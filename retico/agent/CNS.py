import time

from retico.core.abstract import AbstractModule
from retico.core.text.common import SpeechRecognitionIU, GeneratedTextIU
from retico.core.audio.common import SpeechIU, DispatchedAudioIU

from retico.agent.utils import Color as C
from retico.agent.memory import Memory, UserState, AgentState


class CentralNervousSystem(AbstractModule):
    """
    The central nervous system of the agent.
    This is an incremental module which connects Hearing (ASR) & Speech (TTS, AudioDispatcher, AudioStreamer)
    """

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU, DispatchedAudioIU, SpeechIU]

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

        # Activity
        self.agent_speech_ongoing = False
        self.agent_last_speech_end_time = 0.0
        self.backchannel_active = False

        self.user_asr_active = False
        self.user_last_asr_end_time = 0.0
        self.user_turn_active = False
        self.user_last_turn_end_time = 0.0
        self.last_user_state = None

        # VAD
        self.vad_base_active = False
        self.vad_ipu_active = False
        self.vad_fast_active = False

    def vad_callback(self, module, event_name, data):
        now = time.time()
        if event_name == "event_vad_turn_change":
            self.vad_base_active = data["active"]
            if data["active"]:
                self.user.vad_base_on.append(now)
            else:
                self.user.vad_base_off.append(now)

        elif event_name == "event_vad_ipu_change":
            self.vad_ipu_active = data["active"]
            if data["active"]:
                self.user.vad_ipu_on.append(now)
            else:
                self.user.vad_ipu_off.append(now)

        elif event_name == "event_vad_fast_change":
            self.vad_fast_active = data["active"]
            if data["active"]:
                self.user.vad_fast_on.append(now)
            else:
                self.user.vad_fast_off.append(now)

    def finalize_user(self):
        self.user.end_time = time.time()
        self.memory.update(self.user)

        self.user = UserState()
        self.user.vad_base_start = self.vad_base_active
        self.user.vad_ipu_start = self.vad_ipu_active
        self.user.vad_fast_start = self.vad_fast_active
        if self.verbose:
            print("---------- FINALIZE USER  --------------")

    def finalize_agent(self):
        self.agent.end_time = time.time()
        if self.agent.completion >= 1:
            self.agent.utterance = self.agent.planned_utterance
        if self.verbose:
            print(self.agent.utterance)
            print("---------- FINALIZE AGENT --------------")
        self.memory.update(self.agent, agent=True)
        self.agent = AgentState()

    def backchannel(self, text):
        self.backchannel_active = True
        output_iu = self.create_iu()
        output_iu.payload = text
        output_iu.dispatch = True
        self.append(output_iu)

    def start_speech(self, text=None):
        self.agent_speech_ongoing = True
        self.agent.speech_start_time = time.time()
        # self.agent.update("speech_start", time.time() - self.start_time)
        if self.verbose:
            print(C.blue + "######### AGENT SPEECH ##########" + C.end)
        output_iu = self.create_iu()
        if text is None:
            output_iu.payload = self.agent.planned_utterance
        else:
            output_iu.payload = text
        output_iu.dispatch = True
        self.append(output_iu)

    def stop_speech(self, finalize=True):
        """Creates a dummy IUs with dispatch flag false and appends to output. This aborts the speech in the tts"""
        now = time.time()
        self.agent.speech_end_time = now
        self.agent_last_speech_end_time = now
        self.agent_speech_ongoing = False
        if finalize:
            self.finalize_agent()
        output_iu = self.create_iu()
        output_iu.payload = ""
        output_iu.dispatch = False
        self.append(output_iu)

    def process_iu(self, input_iu):
        if isinstance(input_iu, SpeechRecognitionIU):
            self.asr(input_iu)
        elif isinstance(input_iu, SpeechIU):
            self.tts_activity(input_iu)
        elif isinstance(input_iu, DispatchedAudioIU):
            self.audio_dispatcher_activity(input_iu)

    def tts_activity(self, input_iu):
        # if self.verbose:
        #     print("self tts dispatch: ", input_iu.dispatch)
        if input_iu.dispatch:
            self.suspend = False
        else:
            if self.user_asr_active:
                print(C.red, "Interrupted by user", C.end)

    def audio_dispatcher_activity(self, input_iu):
        """
        Listen to
        """
        self.agent.completion = input_iu.completion
        self.agent.utterance = input_iu.completion_words

        if input_iu.completion >= 1:
            print(C.blue + "Speak DONE", C.end)
            if self.backchannel_active:
                self.backchannel_active = False
            now = time.time()
            self.agent.speech_end_time = now
            self.finalize_agent()
            self.agent_last_speech_end_time = now
            self.agent_speech_ongoing = False
        elif input_iu.is_dispatching:
            if not self.agent_speech_ongoing and not self.backchannel_active:
                self.agent_speech_ongoing = True

    def asr(self, input_iu):
        raise NotImplementedError(
            "Must implement asr() for CNS or use a predefined subclass!"
        )

    def run(self, **kwargs):
        self.memory.start_time = time.time()
        super().run(**kwargs)


class CNS(CentralNervousSystem):
    def asr(self, input_iu):
        """Process the ASR input"""
        # activate user-asr state and record when the ASR-onset time
        if not self.user_asr_active:
            now = time.time()
            self.user_asr_active = True
            self.user.start_time = now
            self.user.asr_start_time = now
            if self.verbose:
                print(C.yellow + f"ASR Onset: {self.user_asr_active}" + C.end)

        # update our preliminary utterance
        self.user.prel_utterance = self.user.utterance + input_iu.text
        if input_iu.final:
            self.user_asr_active = False  # asr non active
            now = time.time()
            self.user.asr_end_time = now
            self.user.end_time = now
            self.user_last_asr_end_time = now

            # update the utterance
            self.user.utterance = self.user.prel_utterance

            if self.verbose:
                print(C.yellow + "ASR Final" + C.end)
