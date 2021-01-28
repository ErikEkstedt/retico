import json
import random
import requests
import threading
import time
import re

from retico.core.abstract import AbstractModule
from retico.core.text.common import SpeechRecognitionIU, GeneratedTextIU
from retico.core.audio.common import SpeechIU, DispatchedAudioIU

from retico.agent.utils import Color as C
from retico.agent.utils import write_json

URL_TRP = "http://localhost:5000/trp"


class UserState:
    def __init__(self):
        self.name = "user"
        self.utterance = ""
        self.prel_utterance = ""

        self.asr_start_time = 0.0
        self.asr_end_time = 0.0

        self.turn_completed = 0.0


class AgentState:
    def __init__(self):
        self.name = "agent"
        self.utterance = ""
        self.completion = 0.0
        self.planned_utterance = ""

        self.speech_start_time = 0.0
        self.speech_end_time = 0.0

        self.turn_completed = 0.0

    def __repr__(self):
        s = "AgentState"
        for k, v in self.__dict__.items():
            s += f"\n{k}: {v}"
        s += "\n" + "-" * 30
        return s


class Memory:
    def __init__(self):
        self.turns = []
        self.start_time = 0.0

    def get_context_text(self):
        if len(self.turns) == 0:
            return None

        utterances = []
        last_utt = self.turns[0]["utterance"]
        last_name = self.turns[0]["name"]
        for turn in self.turns[1:]:
            if turn["utterance"] == "":
                continue
            if last_name == turn["name"]:  # consecutive turns
                last_utt = last_utt + " " + turn["utterance"]
            else:
                last_utt = re.sub("^\s", "", last_utt)
                last_utt = re.sub("$\s", "", last_utt)
                last_utt = re.sub("\s\s+", " ", last_utt)
                utterances.append(last_utt)
                last_utt = turn["utterance"]
                last_name = turn["name"]

        last_utt = re.sub("^\s", "", last_utt)
        last_utt = re.sub("$\s", "", last_utt)
        last_utt = re.sub("\s\s+", " ", last_utt)
        utterances.append(last_utt)
        return utterances

    def save(self, savepath):
        data = {"start_time": self.start_time, "turns": self.turns}
        write_json(data, savepath)
        print("Saved memory -> ", savepath)

    def __repr__(self):
        s = "Memory"
        for t in self.turns:
            s += "\n" + str(t)
        s += "\n" + "=" * 50
        return s

    def __getitem__(self, idx):
        return self.turns[idx]

    def update(self, turn):
        if turn["utterance"] != "":
            self.turns.append(turn)


################################################################################


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

        self.user_asr_active = False
        self.user_last_asr_end_time = 0.0

    @property
    def both_inactive(self):
        return not self.user_asr_active and not self.agent_speech_ongoing

    @property
    def both_active(self):
        return self.user_asr_active and self.agent_speech_ongoing

    @property
    def only_user_active(self):
        return self.user_asr_active and not self.agent_speech_ongoing

    @property
    def only_agent_active(self):
        return not self.user_asr_active and self.agent_speech_ongoing

    def finalize_user(self):
        self.user.turn_completed = time.time()
        self.memory.update(self.user.__dict__)
        self.user = UserState()

    def finalize_agent(self):
        self.agent.turn_completed = time.time()
        if self.agent.completion >= 1:
            self.agent.utterance = self.agent.planned_utterance
        self.memory.update(self.agent.__dict__)
        self.agent = AgentState()

    def start_speech(self, text=None):
        self.agent_speech_ongoing = True
        self.agent.speech_start_time = time.time()
        # self.agent.update("speech_start", time.time() - self.start_time)
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
        print("TTS")
        if self.verbose:
            print("self tts dispatch: ", input_iu.dispatch)

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
            print(C.green, "Speak DONE", C.end)
            self.agent_speech_ongoing = False
            now = time.time()
            self.agent.speech_end_time = now
            self.agent_last_speech_end_time = now
        elif input_iu.is_dispatching:
            if not self.agent_speech_ongoing:
                self.agent_speech_ongoing = True

    def asr(self, input_iu):
        """Process the ASR input"""

        # activate user-asr state and record when the ASR-onset time
        if not self.user_asr_active:
            self.user_asr_active = True
            self.user.asr_start_time = time.time()
            if self.verbose:
                print(C.yellow + f"ASR Onset: {self.user_asr_active}" + C.end)

        # update our preliminary utterance
        self.user.prel_utterance = self.user.utterance + input_iu.text
        if input_iu.final:
            self.user_asr_active = False  # asr non active
            now = time.time()
            self.user.asr_end_time = now
            self.user_last_asr_end_time = now

            # update the utterance
            self.user.utterance = self.user.prel_utterance

            if self.verbose:
                print(C.green + "ASR Final" + C.end)

    def run(self, **kwargs):
        self.memory.start_time = time.time()
        super().run(**kwargs)


class FrontalCortexBase:
    DUMMY_RESPONSE = "Now it's my time to talk."
    LOOP_TIME = 0.05  # 50ms  update frequency

    def __init__(
        self,
        central_nervous_system,
        dm=None,
        speak_first=True,
        fallback_duration=4,
        verbose=False,
    ):
        self.cns = central_nervous_system
        self.speak_first = speak_first
        self.dm = dm
        self.verbose = verbose

        self.dialog_ended = False
        self.suspend = False

        self.fallback_duration = fallback_duration

    def check_utterance_dialog_end(self, text=None):
        if "goodbye" in text or "bye" in text:
            return True
        return False

    def is_interrupted(self):
        if self.cns.agent.completion < 0.8:
            return True
        return False

    def fallback_silence(self):
        now = time.time()
        agent_silence = now - self.cns.agent_last_speech_end_time
        user_silence = now - self.cns.user_last_asr_end_time
        latest_activity_time = min(agent_silence, user_silence)
        if latest_activity_time >= self.fallback_duration:
            print("FALLBACK")
            context = self.cns.memory.get_context_text()
            self.cns.agent.planned_utterance, self.dialog_ended = self.dm.get_response(
                context
            )
            self.cns.start_speech(self.cns.agent.planned_utterance)

    def dialog_loop(self):
        raise NotImplementedError("dialog loop not implemented")

    def start_loop(self):
        """Prepares the dialogue_loop and the DialogueState of the agent and the
        interlocutor by resetting the timers.
        This method starts the dialogue_loop."""
        t = threading.Thread(target=self.dialog_loop)
        self.cns.start_time = time.time()
        self.cns.user.asr_end_time = time.time()
        t.start()


class SimpleFC(FrontalCortexBase):
    """
    Starts the dialog by speaking its `DUMMY_RESPONSE`. Listens while the user asr is active and only does a fallback
    action which executes the dummy response if the conversation has been inactive for at leat `fallback_duration`
    seconds.

    Never updates the memory...
    """

    def dialog_loop(self):
        """
        A constant loop which looks at the internal state of the agent, the estimated state of the user and the dialog
        state.

        """
        if self.speak_first:
            if self.dm is not None:
                self.cns.agent.planned_utterance = self.dm.next_question()
            else:
                self.cns.agent.planned_utterance = self.DUMMY_RESPONSE
            self.cns.start_speech(self.cns.agent.planned_utterance)

        last_state = None
        while not self.dialog_ended:
            time.sleep(self.LOOP_TIME)

            if self.suspend:
                continue

            if self.cns.both_inactive:
                if self.verbose and last_state != "both_inactive":
                    print("BOTH INACTIVE")
                    last_state = "both_inactive"
                now = time.time()
                agent_silence = now - self.cns.agent_last_speech_end_time
                user_silence = now - self.cns.user_last_asr_end_time
                latest_activity_time = min(agent_silence, user_silence)
                if latest_activity_time >= self.fallback_duration:
                    self.cns.start_speech(self.cns.agent.planned_utterance)
            elif self.cns.both_active:
                if self.verbose and last_state != "double_talk":
                    print("DOUBLE TALK")
                    last_state = "double_talk"
            elif self.cns.only_user_active:
                if self.verbose and last_state != "only_user":
                    print("USER")
                    last_state = "only_user"
            else:
                if self.verbose and last_state != "only_agent":
                    print("AGENT")
                    last_state = "only_agent"


class ASRFC(FrontalCortexBase):
    """
    Starts the dialog by speaking its `DUMMY_RESPONSE`. Listens while the user asr is active and only does a fallback
    action which executes the dummy response if the conversation has been inactive for at leat `fallback_duration`
    seconds.
    """

    BOTH_ACTIVE = "double_talk"
    BOTH_INACTIVE = "silence"
    ONLY_USER = "only_user"
    ONLY_AGENT = "only_agent"

    def __init__(self, dm, **kwargs):
        super().__init__(**kwargs)
        self.dm = dm

    def respond_or_listen(self):
        end = self.check_utterance_dialog_end(self.cns.user.utterance)
        self.cns.finalize_user()
        if end:
            self.dialog_ended = True
        else:
            context = self.cns.memory.get_context_text()
            (
                self.cns.agent.planned_utterance,
                self.dialog_ended,
            ) = self.dm.get_response(context)
            self.cns.start_speech(self.cns.agent.planned_utterance)

    def dialog_loop(self):
        """
        A constant loop which looks at the internal state of the agent, the estimated state of the user and the dialog
        state.

        """
        if self.speak_first:
            self.cns.agent.planned_utterance, self.dialog_ended = self.dm.get_response()
            self.cns.start_speech(self.cns.agent.planned_utterance)

        last_state = "both_inactive"
        while not self.dialog_ended:
            time.sleep(self.LOOP_TIME)

            if self.cns.both_inactive:
                if self.verbose and last_state != self.BOTH_INACTIVE:
                    print("BOTH INACTIVE")

                if last_state == self.ONLY_USER:
                    self.respond_or_listen()

                elif last_state == self.ONLY_AGENT:
                    print("finalize agent")
                    self.cns.finalize_agent()
                else:
                    self.fallback_silence()
                last_state = self.BOTH_INACTIVE

            elif self.cns.both_active:
                if self.verbose and last_state != self.BOTH_ACTIVE:
                    print("DOUBLE TALK")

                if last_state == self.ONLY_AGENT:
                    if self.is_interrupted():
                        self.cns.stop_speech()
                elif last_state == self.ONLY_USER:
                    finalize = True
                    if self.cns.agent.completion < 0.2:
                        finalize = False
                    self.cns.stop_speech(finalize)

                last_state = self.BOTH_ACTIVE

            elif self.cns.only_user_active:
                if self.verbose and last_state != self.ONLY_USER:
                    print("USER")
                last_state = self.ONLY_USER
            else:
                if self.verbose and last_state != self.ONLY_AGENT:
                    print("AGENT")
                last_state = self.ONLY_AGENT
        print("======== DIALOG DONE ========")


class ASRLMFC(FrontalCortexBase):
    """
    Starts the dialog by speaking its `DUMMY_RESPONSE`. Listens while the user asr is active and only does a fallback
    action which executes the dummy response if the conversation has been inactive for at leat `fallback_duration`
    seconds.
    """

    BOTH_ACTIVE = "double_talk"
    BOTH_INACTIVE = "silence"
    ONLY_USER = "only_user"
    ONLY_AGENT = "only_agent"

    def __init__(self, dm, trp_threshold=0.1, **kwargs):
        super().__init__(**kwargs)
        self.dm = dm
        self.trp_threshold = trp_threshold

    def lm_eot(self, text):
        json_data = {"text": text}
        response = requests.post(URL_TRP, json=json_data)
        d = json.loads(response.content.decode())
        return d["trp"][-1]  # only care about last token

    def respond_or_listen(self):
        context = self.cns.memory.get_context_text()
        current_utt = re.sub("^\s", "", self.cns.user.utterance)
        current_utt = re.sub("$\s", "", current_utt)
        current_utt = re.sub("\s\s+", " ", current_utt)
        context.append(current_utt)

        for i, utt in enumerate(context):
            if i % 2 == 0:
                print(C.blue + utt, C.end)
            else:
                print(C.yellow + utt, C.end)

        trp = self.lm_eot(context)

        if trp >= self.trp_threshold:
            print(C.green + f"EOT recognized: {round(trp, 3)}" + C.end)
            self.cns.finalize_user()
            context = self.cns.memory.get_context_text()
            self.cns.agent.planned_utterance, self.dialog_ended = self.dm.get_response(
                context
            )
            self.cns.start_speech(self.cns.agent.planned_utterance)
        else:
            print(C.red + f"listen: {1-round(trp, 3)}" + C.end)
            if random.random() < 0.4:
                self.cns.start_speech("Go on.")

        if self.check_utterance_dialog_end(current_utt):
            self.dialog_ended = True
            return True

    def dialog_loop(self):
        """
        A constant loop which looks at the internal state of the agent, the estimated state of the user and the dialog
        state.

        """
        if self.speak_first:
            self.cns.agent.planned_utterance, self.dialog_ended = self.dm.get_response()
            self.cns.start_speech(self.cns.agent.planned_utterance)

        last_state = "both_inactive"
        while not self.dialog_ended:
            time.sleep(self.LOOP_TIME)

            if self.cns.both_inactive:
                if self.verbose and last_state != self.BOTH_INACTIVE:
                    print("BOTH INACTIVE")

                if last_state == self.ONLY_USER:
                    end = self.respond_or_listen()
                    if end:
                        print("END EVERYTHING")
                        self.dialog_ended = True
                        break
                elif last_state == self.ONLY_AGENT:
                    print("finalize agent")
                    self.cns.finalize_agent()
                else:
                    self.fallback_silence()
                last_state = self.BOTH_INACTIVE

            elif self.cns.both_active:
                if self.verbose and last_state != self.BOTH_ACTIVE:
                    print("DOUBLE TALK")

                if last_state == self.ONLY_AGENT:
                    if self.is_interrupted():
                        self.cns.stop_speech()
                elif last_state == self.ONLY_USER:
                    finalize = True
                    if self.cns.agent.completion < 0.2:
                        finalize = False
                    self.cns.stop_speech(finalize)

                last_state = self.BOTH_ACTIVE
            elif self.cns.only_user_active:
                if self.verbose and last_state != self.ONLY_USER:
                    print("USER")
                last_state = self.ONLY_USER
            else:
                if self.verbose and last_state != self.ONLY_AGENT:
                    print("AGENT")
                last_state = self.ONLY_AGENT
        print("======== DIALOG DONE ========")


def test_central_nervous_system(args):
    from retico.agent import Hearing, Speech

    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        use_asr=True,
        record=False,
        debug=False,
    )
    speech = Speech(
        chunk_time=args.speech_chunk_time,
        sample_rate=args.speech_sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        tts_client="amazon",
        output_word_times=True,
        debug=False,
    )
    cns = CentralNervousSystem(verbose=args.verbose)
    frontal = SimpleFC(central_nervous_system=cns, verbose=args.verbose)

    hearing.asr.subscribe(cns)
    speech.audio_dispatcher.subscribe(cns)
    speech.tts.subscribe(cns)
    cns.subscribe(speech.tts)

    hearing.run_components()
    speech.run()
    cns.run()  # starts the loop

    frontal.start_loop()
    input()

    hearing.stop_components()
    speech.tts.shutdown()
    speech.stop()
    cns.stop()


def test_asr_fc(args):
    from retico.agent import Hearing, Speech
    from retico.agent.dm import DM

    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        use_asr=True,
        record=False,
        debug=False,
    )
    speech = Speech(
        chunk_time=args.speech_chunk_time,
        sample_rate=args.speech_sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        tts_client="amazon",
        output_word_times=True,
        debug=False,
    )
    cns = CentralNervousSystem(verbose=args.verbose)
    dm = DM()
    frontal = ASRFC(
        dm=dm,
        central_nervous_system=cns,
        fallback_duration=args.fallback_duration,
        verbose=args.verbose,
    )

    hearing.asr.subscribe(cns)
    speech.audio_dispatcher.subscribe(cns)
    speech.tts.subscribe(cns)
    cns.subscribe(speech.tts)

    hearing.run_components()
    speech.run()
    cns.run()  # starts the loop

    frontal.start_loop()

    input()

    cns.memory.save("dialog_log.json")
    hearing.stop_components()
    speech.tts.shutdown()
    speech.stop()
    cns.stop()


def test_asr_lm_fc(args):
    from retico.agent import Hearing, Speech
    from retico.agent.dm import DM

    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        use_asr=True,
        record=False,
        debug=False,
    )
    speech = Speech(
        chunk_time=args.speech_chunk_time,
        sample_rate=args.speech_sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        tts_client="amazon",
        output_word_times=True,
        debug=False,
    )
    cns = CentralNervousSystem(verbose=args.verbose)
    dm = DM()
    frontal = ASRLMFC(
        dm=dm,
        central_nervous_system=cns,
        trp_threshold=args.trp,
        fallback_duration=args.fallback_duration,
        verbose=args.verbose,
    )

    hearing.asr.subscribe(cns)
    speech.audio_dispatcher.subscribe(cns)
    speech.tts.subscribe(cns)
    cns.subscribe(speech.tts)

    hearing.run_components()
    speech.run()
    cns.run()  # starts the loop

    frontal.start_loop()

    input("DIALOG\n")
    cns.memory.save("dialog_asr_lm.json")

    hearing.stop_components()
    speech.tts.shutdown()
    speech.stop()
    cns.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DialogState")
    parser.add_argument("--chunk_time", type=float, default=0.01)
    parser.add_argument("--sample_rate", type=int, default=16000)
    parser.add_argument("--speech_chunk_time", type=float, default=0.1)
    parser.add_argument("--speech_sample_rate", type=int, default=16000)
    parser.add_argument("--bytes_per_sample", type=int, default=2)
    parser.add_argument("--trp", type=float, default=0.1)
    parser.add_argument("--fallback_duration", type=float, default=2)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--test", type=str, default="cns")
    args = parser.parse_args()

    if args.test == "cns":
        test_central_nervous_system(args)
    elif args.test == "asr":
        test_asr_fc(args)
    elif args.test == "asrlm":
        test_asr_lm_fc(args)
    else:
        print(f"{args.test} not implemented. Try: [cns, asr]")
