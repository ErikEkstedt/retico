import time
import threading

from retico.core.abstract import AbstractModule
from retico.core.text.common import SpeechRecognitionIU, GeneratedTextIU
from retico.core.audio.common import SpeechIU, DispatchedAudioIU

from retico.agent.utils import Color as C

"""
Determine start of user turn  vad/asr
Determine end   of user turn  vad/asr/eot

TurnStates: Agent, User, Undecided

    - User:  Listen to the user and wait for an EOT event
    - Agent: Create speech until completed.
        - listen to user and decide to continue or be silent
    - Undecided: There is no clear occupant of the turn-floor.
        - Context dependent action selection
        - Both vs None
        - Agent -> None -> ? Should we wait for response or take initiative?
        - User -> None -> ? Should we reply?
        - Agent -> Both -> ?  Are we at the end of our utterance or at the very beginning?
        - User -> Both -> ? The agent produced overlap (not currently supposed to happen)
"""


class SpeakerTurnState:
    def __init__(self, name=""):
        self.name = name
        self.current_utterance = ""
        self.completion = 0
        self.finalized = None

    def update(self, property, value):
        self.__setattr__(property, value)

    def __repr__(self):
        s = f"name: {self.name}\n"
        for prop, val in vars(self).items():
            if not prop == "name":
                s += f"{prop}: {val}\n"
        s += "-" * 50
        return s

    def finalize(self, time=0):
        if self.name == "user":
            if self.prel_utterance != self.current_utterance:
                self.current_utterance = self.prel_utterance
            self.prel_utterance = ""
        self.finalized = time

    def to_dict(self):
        d = {}
        for prop, value in vars(self).items():
            d[prop] = value
        return d


class TurnState:
    STATES = ["undecided", "agent", "user"]

    def __init__(self, state, rel_start_time=0):
        assert state in self.STATES, "State must be on of {self.STATES}"
        self.state = state
        self.time = time.time() - rel_start_time

    def get(self, name):
        return self.__getattribute__(name)


class TurnTakingModule(AbstractModule):
    TURN_STATES = ["undecided", "agent", "user"]
    LOOP_TIME = 0.05
    EVENT_DIALOG_FINISH = "event_dialog_finish"

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU, DispatchedAudioIU, SpeechIU]

    @staticmethod
    def output_iu():
        return GeneratedTextIU

    def __init__(self, eot=None, vad_slow=None, nlg=None, verbose=False, **kwargs):
        super().__init__(**kwargs)
        self.dialog_ended = False
        self.speak_first = True
        self.max_silence_time = 4
        self.initial_response = "Hi there, how can I help you today?"
        self.verbose = verbose

        self.user = SpeakerTurnState(name="user")
        self.agent = SpeakerTurnState(name="agent")
        self.history = []
        self.utterance_history = []

        # Keep track of user turn
        self.user_turn_ongoing = False
        self.user_asr_active = False  # ASR Activity

        # Keep track of user turn
        self.agent_turn_initialized = False  # before any audio has reached the speakers
        self.agent_turn_ongoing = False
        self.agent_speech_ongoing = False

        # keep track of time in the last undecided state
        self.undecided_start = time.time()

        self.turn_state = None
        self.turn_state_history = []

        # Components
        self.vad_slow = vad_slow
        if vad_slow is not None:
            self.vad_slow.event_subscribe(
                vad_slow.EVENT_VAD_CHANGE, self.vad_slow_callback
            )
        self.nlg = nlg
        self.eot = eot

    @property
    def turn_undecided(self):
        both = self.user_turn_ongoing and self.agent_turn_ongoing
        none = not self.user_turn_ongoing and not self.agent_turn_ongoing
        return both or none

    def get_utterance_history(self):
        utterances = []
        last_utt = self.history[0]["current_utterance"]
        last_name = self.history[0]["name"]
        for turn in self.history[1:]:
            if turn["current_utterance"] == "":
                continue

            if last_name == turn["name"]:
                last_utt += " " + turn["current_utterance"]
            else:
                utterances.append(last_utt)
                last_utt = turn["current_utterance"]
                last_name = turn["name"]
        utterances.append(last_utt)
        return utterances

    def finalize_user(self):
        self.user.finalize(time.time() - self.start_time)
        self.user.current_utterance = self.user.current_utterance.strip()
        self.history.append(self.user.to_dict())
        self.user = SpeakerTurnState("user")
        self.user_turn_ongoing = False

        if self.nlg is not None:
            # context = self.get_total_dialog()
            context = self.get_utterance_history()
            print(context)
            self.planned_utterance = self.nlg.generate_response(context)
        else:
            self.planned_utterance = "Yes, now it's my turn to speak."

    def finalize_agent(self):
        if self.agent.current_utterance != "":
            self.agent.finalize(time.time() - self.start_time)
            self.agent.current_utterance = self.agent.current_utterance.strip()
            self.history.append(self.agent.to_dict())
        self.agent = SpeakerTurnState("agent")
        self.agent_turn_ongoing = False

    def speak(self, text=None):
        if text is not None:
            planned_utterance = text
        else:
            planned_utterance = self.planned_utterance
        self.agent.update("planned_utterance", planned_utterance)
        self.agent.update("speak_action", time.time() - self.start_time)
        self.agent_turn_initialized = True
        output_iu = self.create_iu()
        output_iu.payload = planned_utterance
        output_iu.dispatch = True
        self.append(output_iu)

    def stop_speaking(self):
        output_iu = self.create_iu()
        output_iu.payload = ""
        output_iu.dispatch = False
        self.append(output_iu)
        time.sleep(0.5)

    def is_interrupted(self):
        return self.agent.completion < 0.8

    def update_turn_state(self):
        updated_turn = False
        if self.turn_undecided:
            if not self.turn_state.state == "undecided":
                self.turn_state_history.append(self.turn_state)
                self.turn_state = TurnState("undecided", self.start_time)
                self.undecided_start = time.time()
                updated_turn = True
        elif self.user_turn_ongoing:
            if not self.turn_state.state == "user":
                self.turn_state_history.append(self.turn_state)
                self.turn_state = TurnState("user", self.start_time)
                updated_turn = True
        else:
            if not self.turn_state.state == "agent":
                self.turn_state_history.append(self.turn_state)
                self.turn_state = TurnState("agent", self.start_time)
                updated_turn = True

        if updated_turn and self.verbose:
            print(
                C.yellow
                + f"New turn state: {self.turn_state_history[-1].state} -> {self.turn_state.state}"
                + C.end
            )

    def start_dialog(self):
        """Prepares the dialogue_loop and the DialogueState of the agent and the
        interlocutor by resetting the timers.
        This method starts the dialogue_loop."""
        t = threading.Thread(target=self.dialog_loop)
        t.start()

    def dialog_loop(self):
        if self.speak_first:
            self.speak(self.initial_response)

        self.suspend = False
        while not self.dialog_ended:
            while self.suspend:
                time.sleep(self.LOOP_TIME)

            if (
                self.turn_state.state == "undecided"
                and time.time() - self.undecided_start > self.max_silence_time
            ):
                self.speak()
                self.suspend = True
            elif len(self.turn_state_history) > 0:
                if (
                    self.turn_state_history[-1].state == "agent"
                    and self.turn_state.state == "undecided"
                ):
                    if self.is_interrupted():
                        self.stop_speaking()
                elif (
                    self.turn_state_history[-1].state == "user"
                    and self.turn_state.state == "undecided"
                ):
                    self.speak()
                    self.suspend = True

            time.sleep(self.LOOP_TIME)

        self.event_call("EVENT_END")

    def process_iu(self, input_iu):
        if isinstance(input_iu, SpeechRecognitionIU):
            self.asr(input_iu)
        elif isinstance(input_iu, SpeechIU):
            self.tts_activity(input_iu)
        elif isinstance(input_iu, DispatchedAudioIU):
            self.audio_dispatcher_activity(input_iu)

    def run(self, **kwargs):
        self.start_time = time.time()
        self.turn_state = TurnState("undecided", self.start_time)
        if self.vad_slow is not None:
            self.vad_slow.run()
        super().run(**kwargs)

    def stop(self, **kwargs):
        if self.vad_slow is not None:
            self.vad_slow.stop()
        super().stop(**kwargs)

    def vad_slow_callback(self, module, event_name, data):
        if data["is_speaking"]:
            self.user_active = True
            print("User VAD Active")
        else:
            self.user_active = False
            print("User VAD Silent")
        self.update_turn_state()

    def tts_activity(self, input_iu):
        if input_iu.dispatch:
            self.agent_turn_ongoing = True
            self.suspend = False
        else:
            if self.user_turn_ongoing:
                print(C.red, "Interrupted by user", C.end)
                self.finalize_agent()
        self.update_turn_state()

    def audio_dispatcher_activity(self, input_iu):
        """
        Listen to
        """
        self.agent.update("completion", input_iu.completion)
        self.agent.update("current_utterance", input_iu.completion_words)

        if input_iu.completion >= 1:
            print(C.green, "Speak DONE", C.end)
            self.agent_speech_ongoing = False
            self.agent.update("audio_end", time.time() - self.start_time)
            self.agent.update("current_utterance", self.agent.planned_utterance)
            self.finalize_agent()
            self.update_turn_state()
        elif input_iu.is_dispatching:
            if not self.agent_speech_ongoing:
                self.agent_speech_ongoing = True
                self.agent.update("audio_start", time.time() - self.start_time)

    def asr(self, *args, **kwargs):
        raise NotImplementedError()


class TurnTakingBaseline(TurnTakingModule):
    def asr(self, input_iu):
        if not self.user_asr_active:
            self.user.update("asr_onset", time.time() - self.start_time)
            self.user_asr_active = True
            self.user_turn_ongoing = True
            # print(C.yellow + f"ASR Onset: {self.user_asr_active}" + C.end)

        self.user.prel_utterance = self.user.current_utterance + input_iu.text

        if "goodbye" in input_iu.text:
            self.finalize_user()
            self.dialog_ended = True
            self.speak("Goodbye!")

        if input_iu.final:
            self.user_asr_active = False
            self.user.update("asr_final", time.time() - self.start_time)
            self.user.current_utterance = self.user.prel_utterance

            if self.eot is None:
                # print(C.green + "ASR EOT" + C.end)
                self.user_turn_ongoing = False
                self.finalize_user()
                self.update_turn_state()
        self.update_turn_state()


def test_turntaking():
    from retico.agent import Hearing, Speech, VAD
    from retico.agent.nlg import NLG
    from retico.agent.utils import write_json

    import argparse

    parser = argparse.ArgumentParser(description="DialogState")
    parser.add_argument("--onset", type=float, default=0.2)
    parser.add_argument("--offset", type=float, default=0.8)
    parser.add_argument("--chunk_time", type=float, default=0.01)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    sample_rate = 16000
    bytes_per_sample = 2
    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=sample_rate,
        bytes_per_sample=bytes_per_sample,
        use_asr=True,
        record=False,
        debug=False,
    )
    speech = Speech(
        chunk_time=0.1,
        sample_rate=16000,
        bytes_per_sample=2,
        tts_client="amazon",
        output_word_times=True,
        debug=False,
    )
    vad_slow = VAD(
        chunk_time=args.chunk_time,
        onset_time=0.3,
        offset_time=2.0,
        debug=False,
    )
    nlg = NLG()
    turntaking = TurnTakingBaseline(nlg=nlg, verbose=args.verbose)

    hearing.asr.subscribe(turntaking)
    hearing.vad_frames.subscribe(vad_slow)
    speech.audio_dispatcher.subscribe(turntaking)
    speech.tts.subscribe(turntaking)
    turntaking.subscribe(speech.tts)

    hearing.run_components()
    speech.run()

    turntaking.run()  # starts the loop
    turntaking.start_dialog()
    while not turntaking.dialog_ended:
        time.sleep(0.1)

    hearing.stop_components()
    speech.tts.shutdown()
    speech.stop()
    turntaking.stop()

    write_json(turntaking.history, "dialog_log.json")
    # print("DIALOG HISTORY")
    # for turn in turntaking.history:
    #     color = C.blue
    #     if turn["name"] == "user":
    #         color = C.yellow
    #     for k, v in turn.items():
    #         print(color + f"{k}: {v}", C.end)
    #     print("-" * 20)

    import sys

    sys.exit()


if __name__ == "__main__":
    # test_spoken_dialog_state()
    test_turntaking()
