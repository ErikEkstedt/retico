import time
from os.path import split
from os import makedirs
import numpy as np

from retico.core.abstract import AbstractModule
from retico.core.text.common import SpeechRecognitionIU, GeneratedTextIU
from retico.core.audio.common import DispatchedAudioIU

# from retico.core.audio.common import SpeechIU, DispatchedAudioIU

from retico.agent.utils import clean_whitespace, write_json, Color as C
from retico.agent.memory import Memory, UserState, AgentState


class CNS(AbstractModule):
    """
    CentralNervousSystem
    --------------------

    The central nervous system of the agent.
    This is an incremental module which connects Hearing (ASR) & Speech (TTS, AudioDispatcher, AudioStreamer)
    """

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU, DispatchedAudioIU]

    @staticmethod
    def output_iu():
        return GeneratedTextIU

    def __init__(self, verbose=False, **kwargs):
        super().__init__(**kwargs)
        self.verbose = verbose

        # Memory
        self.user = UserState()
        self.agent = AgentState()
        self.memory = Memory()
        self.utterance_history = []
        self.start_time = 0

        # Used if agent is interrupted but did not finish a sufficient
        # amount of the utterances
        self.ask_question_again = False

        # Dialog Turn States
        self.dialog_states = [{"state": "start", "time": -1}]

        ###################################################################
        # AGENT
        ###################################################################
        # Activity
        # all times that the system is predicted to take the turn
        self.agent_turn_active = False
        self.agent_last_speech_end_time = 0.0
        self.agent_turn_on = []
        self.agent_turn_off = []
        self.agent_turn_predicted = False
        self.agent_turn_predicted_on = []
        self.agent_interrupted = []

        ###################################################################
        # USER
        ###################################################################
        # ASR
        # Keeps track of the ASR activity
        self.asr_active = False  # quick way to access activity
        self.asr_on = []  # all ONset times
        self.asr_off = []  # all OFFset times

        # VAD
        # The CNS listens to callbacks in the VADModule.
        #
        # Keeps track of the vad states of the interaction
        # *_active is simply if its activated or not/on or off
        # vad_*_on/off stores all onset/offset times
        self.vad_ipu_active = False
        self.vad_ipu_on = []  # faster ipu vad
        self.vad_ipu_off = []
        self.vad_turn_active = False
        self.vad_turn_on = []  # slower vad for fallback
        self.vad_turn_off = []  # slower vad for fallback

        # Turn
        # A user turn may depend on both the VAD & ASR values
        # the turn-taking policies define when turns starts/ends
        self.user_turn_active = False  # quick access to activity state
        self.user_turn_on = []  # all turn onsets
        self.user_turn_off = []  # all turn offsets

    def vad_callback(self, module, event_name, data):
        now = time.time()
        if event_name == "event_vad_ipu_change":
            self.vad_ipu_active = data["active"]
            if data["active"]:
                self.vad_ipu_on.append(now)
            else:
                self.vad_ipu_off.append(now)
        if event_name == "event_vad_turn_change":
            self.vad_turn_active = data["active"]
            if data["active"]:
                self.vad_turn_on.append(now)
            else:
                self.vad_turn_off.append(now)

    def _speak(self, utterance):
        output_iu = self.create_iu()
        output_iu.payload = utterance
        output_iu.dispatch = True
        self.append(output_iu)

    def init_agent_turn(self, text):
        self.agent = AgentState()
        self.agent.planned_utterance = text
        self.agent_turn_active = True
        self.agent_turn_on.append(self.agent.start_time)  # must be after .finalize
        self._speak(text)
        # if self.verbose:
        #     print(C.green + "######### AGENT TURN ##########" + C.end)

    def finalize_agent(self):
        self.agent_turn_active = False
        if self.agent.utterance != "":
            self.agent.finalize()
            self.agent_turn_off.append(self.agent.end_time)  # must be after .finalize
            self.memory.update(self.agent, agent=True)

    def init_user_turn(self, user_state=None):
        if user_state == None:
            self.user = UserState()
            self.user_turn_on.append(self.user.start_time)  # must be after .finalize
        else:
            # retriggered an erroneous EOT guess by interruption
            # use the last user state
            # change the last dialog state to both
            self.user = user_state
        self.user_turn_active = True

    def finalize_user(self):
        self.user.finalize()
        self.user_turn_active = False
        self.user_turn_off.append(self.user.end_time)  # must be after .finalize
        self.memory.update(self.user)

    def stop_speech(self, finalize=True):
        """Creates a dummy IUs with dispatch flag false and appends to output. This aborts the speech in the tts. The
        finalize flag is by default True but can be set to false for backchannels and the like which should not
        influence the dialog"""
        if self.agent_turn_active:
            now = time.time()
            self.agent_last_speech_end_time = now
            self.agent_speech_ongoing = False
            self.agent_interrupted.append(now)
            if finalize:
                self.agent.interrupted = True
                self.finalize_agent()
            output_iu = self.create_iu()
            output_iu.payload = ""
            output_iu.dispatch = False
            self.append(output_iu)

    def process_iu(self, input_iu):
        if isinstance(input_iu, SpeechRecognitionIU):
            self.asr(input_iu)
        elif isinstance(input_iu, DispatchedAudioIU):
            self.audio_dispatcher_activity(input_iu)

    def asr(self, input_iu):
        """Process the ASR input"""
        # activate user-asr state and record when the ASR-onset time
        now = time.time()
        if not self.asr_active:
            self.asr_active = True
            self.asr_on.append(now)
            if self.verbose:
                print(C.cyan + f"ASR Onset: {self.asr_active}" + C.end)

        # update our preliminary utterance
        self.user.prel_utterance = self.user.utterance + input_iu.text

        if input_iu.final:
            self.asr_active = False  # asr non active
            self.asr_off.append(now)

            # update the utterance
            self.user.utterance = self.user.prel_utterance
            if self.verbose:
                print(C.cyan + "ASR Final" + C.end)

    def audio_dispatcher_activity(self, input_iu):
        """
        Keeps track of the agents ongoing turn.

        Adds completed words, as spoken, to the agent turn data.
        If the current turn is finished we finalize the agent and record relevant times
        """
        if self.agent_turn_active:
            self.agent.completion = input_iu.completion
            if hasattr(input_iu, "completion_words"):
                self.agent.utterance = input_iu.completion_words

        if input_iu.completion >= 1:  # done with turn
            self.ask_question_again = False
            self.finalize_agent()
        elif input_iu.is_dispatching:
            if not self.agent_turn_active:
                self.agent_speech_active = True

    def run(self, **kwargs):
        self.memory.start_time = time.time()
        super().run(**kwargs)

    def save(self, savepath):
        turns = self.memory.finalize_turns()

        states = []
        for state in self.dialog_states[1:]:  # dont care about dummy start state
            state["time"] -= self.start_time
            states.append(state)

        data = {
            "turns": turns,
            "vad_ipu_on": list(np.array(self.vad_ipu_on) - self.start_time),
            "vad_ipu_off": list(np.array(self.vad_ipu_off) - self.start_time),
            "vad_turn_on": list(np.array(self.vad_turn_on) - self.start_time),
            "vad_turn_off": list(np.array(self.vad_turn_off) - self.start_time),
            "asr_on": list(np.array(self.asr_on) - self.start_time),
            "asr_off": list(np.array(self.asr_off) - self.start_time),
            "agent_turn_on": list(np.array(self.agent_turn_on) - self.start_time),
            "agent_turn_off": list(np.array(self.agent_turn_off) - self.start_time),
            "agent_interrupted": list(
                np.array(self.agent_interrupted) - self.start_time
            ),
            "dialog_states": states,
        }

        dirpath = split(savepath)[0]
        if dirpath != "":
            makedirs(dirpath, exist_ok=True)
        write_json(data, savepath)
        print("Saved memory -> ", savepath)
