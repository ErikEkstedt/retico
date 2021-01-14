import time
import re
import threading

from retico.core.abstract import AbstractModule
from retico.core.audio.common import DispatchedAudioIU
from retico.core.text.common import GeneratedTextIU

from retico.agent.common import EotIU, TurnTakingIU, SadIU
from retico.agent.utils import Color as C


class SpeakerState:
    def __init__(self, speaker="other"):
        self.speaker = speaker
        self.utter_end = 0
        self.utter_start = 0
        self.utterance = ""
        self.planned_utterance = ""
        self.is_active = 0
        self.completion = 0

    def reset(self):
        self.utter_end = 0
        self.utter_start = 0
        self.is_active = 0
        self.completion = 0

    def finalize(self):
        self.utter_end = time.time()
        self.duration = self.utter_end - self.utter_start
        return self.to_dict()

    def to_dict(self):
        """
        A turn has a field for the speaker and ipus. A turn may consist of multiple IPU (each recognized separately from
        the eot-module).

        A turn by the agent might have a planned-utterance which maybe did not finish before the user interrupts. We
        store both.
        """
        turn = {
            "speaker": self.speaker,
            "ipus": [
                {
                    "utterance": self.utterance,
                    "utter_start": self.utter_start,
                    "utter_end": self.utter_end,
                    "duration": self.duration,
                    "completion": self.completion,
                }
            ],
        }
        if self.planned_utterance != "":
            turn["ipus"][0]["planned_utterance"] = self.planned_utterance
        return turn


class DialogHistory:
    def __init__(self):
        self.turns = []

    def update(self, state):
        dict_state = state.to_dict()
        if len(self.turns) > 0:
            if dict_state["speaker"] == self.turns[-1]["speaker"]:
                # append the ipu to the last turn
                self.turns[-1]["ipus"] += dict_state["ipus"]
            else:
                self.turns.append(dict_state)
        else:
            self.turns.append(dict_state)

    def print_dialog(self):
        turns = self.get_dialog()
        print("History")
        for turn in turns:
            speaker = turn["speaker"]
            if speaker == "me":
                color = C.blue
            else:
                color = C.yellow
            print(color + "\t" + speaker)
            print(f"\ttext: ", turn["text"])
            if "planned_utterance" in turn:
                print(f"\tplanned: ", turn["planned_utterance"])
            print(f"\tduration: ", turn["duration"])
            print(f"\tcompletion: ", str(turn["completion"]) + C.end)

    def get_dialog(self):
        turns = []
        for turn in self.turns:
            tmp_turn = {
                "speaker": turn["speaker"],
            }
            text = []
            planned = []
            completions = []
            for ipu in turn["ipus"]:
                text.append(ipu["utterance"])
                completions.append(ipu["completion"])
                if "planned_utterance" in ipu:
                    planned.append(ipu["planned_utterance"])

            planned = re.sub("\s\s+", " ", " ".join(planned))
            if planned != "":
                tmp_turn["planned_utterance"] = planned
            tmp_turn["text"] = re.sub("\s\s+", " ", " ".join(text).strip())
            tmp_turn["completion"] = completions
            tmp_turn["duration"] = (
                turn["ipus"][-1]["utter_end"] - turn["ipus"][0]["utter_start"]
            )
            turns.append(tmp_turn)
        return turns


class TurnTaking(AbstractModule):
    """
    This module is responsible for Turn-Organization.

    When the EOT-input is false we assume that the other person is speaking.

    THis module must handle:
        * Start speaking when the user is estimated to be done with their turn
        * Stop speaking if the user starts talking while the agent is active
        * Start speaking if there is some threshold silence level detected
    """

    SILENCE_COOLDOWN = 0.5
    SLEEP_TIME = 0.1
    EVENT_SILENCE = "silence"

    @staticmethod
    def input_ius():
        return [GeneratedTextIU, DispatchedAudioIU, EotIU, SadIU]

    @staticmethod
    def output_iu():
        return TurnTakingIU

    def __init__(self, debug=False, **kwargs):
        super().__init__(**kwargs)

        self.turn_state = "start"
        self.turn_state_start = 0
        self.last_turn_state = "start"

        self.state = SpeakerState("me")
        self.state_other = SpeakerState("other")
        self.dialog_history = DialogHistory()
        self.dialogue_finished = False

        # parameter for a sleep mechanism when forced to be silent
        self.silence_time = 0

        self.debug = debug

    def update_turn_state(self):
        if self.state_other.is_active:
            if self.state.is_active:
                new_turn_state = "both"
            else:
                new_turn_state = "other"
        else:
            if self.state.is_active:
                new_turn_state = "self"
            else:
                new_turn_state = "none"

        if new_turn_state != self.turn_state:
            self.last_turn_state = self.turn_state
            self.turn_state = new_turn_state
            self.turn_state_start = time.time()
            if self.debug:
                print("TurnState: ", self.turn_state)

            if self.turn_state == "none":
                self.dialog_history.print_dialog()

    def action(self):
        if self.last_turn_state == "other":
            if self.turn_state == "none":
                self.output(
                    "speak"
                )  # , meta_data={"history": self.dialog_history.get_dialog()})
        elif self.last_turn_state == "self":
            if self.turn_state == "both":
                # be silence on any interruption
                # must finalize and add to history here.
                # Could not get dispatchedAdudio to trigger dispatch=false
                if 0.1 < self.state.completion < 0.95 or self.state.completion == 1:
                    self.state.finalize()
                    self.silence_time = time.time()
                    self.dialog_history.update(self.state)
                    self.state.reset()
                    # self.update_history(self.state)
                    self.output(
                        "silence"
                    )  # , meta_data={"history": self.get_history()})

    def handle_planned_response(self, input_iu):
        self.state.planned_utterance = input_iu.payload

    def handle_eot(self, input_iu):
        if input_iu.eot:
            # the 'other's turn has ended. Save the data and store in history
            if input_iu.text != "":
                self.state_other.utterance = input_iu.text
            if "goodbye" in input_iu.text:
                self.dialogue_finished = True
            self.state_other.completion = input_iu.probability
            self.state_other.finalize()
            self.dialog_history.update(self.state_other)
            self.state_other.reset()
            self.state.is_active = False
            # self.update_history(self.state_other)
        else:
            self.state_other.is_active = True
            self.state_other.utter_start = time.time()
        self.update_turn_state()
        self.action()

    def listen_self(self, input_iu):
        # Record utterance end/start time
        if time.time() - self.silence_time <= self.SILENCE_COOLDOWN:
            return

        if not self.state.is_active and input_iu.is_dispatching:
            self.state.utter_start = time.time()
            self.state.is_active = True
        self.state.completion = input_iu.completion
        self.update_turn_state()
        self.action()

    def handle_sad(self, input_iu):
        pass

    def output(self, action, meta_data={}):
        output_iu = self.create_iu()
        output_iu.set_action(action, meta_data=meta_data)
        self.append(output_iu)

    def process_iu(self, input_iu):
        if isinstance(input_iu, EotIU):
            self.handle_eot(input_iu)
        elif isinstance(input_iu, DispatchedAudioIU):
            self.listen_self(input_iu)
        elif isinstance(input_iu, GeneratedTextIU):
            self.handle_planned_response(input_iu)
        elif isinstance(input_iu, SadIU):
            self.handle_sad(input_iu)
        return None

    # def prepare_run(self):
    #     """Prepares the dialogue_loop and the DialogueState of the agent and the
    #     interlocutor by resetting the timers.
    #     This method starts the dialogue_loop."""
    #     t = threading.Thread(target=self.dialogue_loop)
    #     t.start()

    def dialogue_loop(self):
        """
        The dialogue loop that continuously checks the state of the agent and
        the interlocutor to determine what action to perform next.
        """
        last_state = -1
        while not self.dialogue_finished:
            # Suspend execution until something happens
            # not_first = True
            # while self.suspended:
            #     if not_first:
            #         print("suspend")
            #         not_first = False
            #     time.sleep(self.SLEEP_TIME)

            if not self.dialogue_started and self.first_utterance:
                self.dialogue_started = True
                # self.next_response = self.initial_utterance
                self.speak()
                # self.suspended = True

            if self.both_silent:
                # 0
                if self.verbose:
                    if last_state != 0:
                        print(C.yellow + "\tState: BOTH silent" + C.end)
                        last_state = 0
            elif self.only_i_speak:
                # 1
                if self.verbose:
                    if last_state != 1:
                        print(C.blue + "\tState: I speak" + C.end)
                        last_state = 1
            elif self.only_they_speak:
                # 2
                if self.verbose:
                    if last_state != 2:
                        print(C.cyan + "\tState: THEY speak" + C.end)
                        last_state = 2
            elif self.both_speak:
                if self.verbose:
                    if last_state != 3:
                        print(C.pink + "\tState: BOTH SPEAK" + C.end)
                        last_state = 3

                # self.silence()

            time.sleep(self.SLEEP_TIME)


class NLGSimple(AbstractModule):
    """
    This module is responsible for Turn-Organization.

    When the EOT-input is false we assume that the other person is speaking.


    THis module must handle:
        * Start speaking when the user is estimated to be done with their turn
        * Stop speaking if the user starts talking while the agent is active
        * Start speaking if there is some threshold silence level detected
    """

    SLEEP_TIME = 0.1
    EVENT_SILENCE = "silence"
    EVENT_SPEAK = "speak"

    @staticmethod
    def input_ius():
        return [TurnTakingIU]

    @staticmethod
    def output_iu():
        return GeneratedTextIU

    def __init__(self, debug=False, **kwargs):
        super().__init__(**kwargs)
        self.utterance = "I can do many things. I can talk and listen. I can be interrupted and I can initiate the turn.  Cool huh?"
        self.debug = debug

    def silence(self):
        """Silence the current utterance of the agent. For this, a new
        DialogueActIU is created with the dispatch-flag set to False.

        This method calls the event `EVENT_SILENCE` and suspends the dialog
        loop."""
        output_iu = self.create_iu(None)
        output_iu.payload = ""
        output_iu.dispatch = False
        self.append(output_iu)
        self.event_call(self.EVENT_SILENCE)

    def speak(self, input_iu):
        output_iu = self.create_iu(None)
        output_iu.payload = self.utterance
        output_iu.dispatch = True
        self.append(output_iu)
        self.event_call(self.EVENT_SPEAK)

    def process_iu(self, input_iu):
        if input_iu.action == "speak":
            self.speak(input_iu)
        elif input_iu.action == "silence":
            self.silence()


def test_turntaking_vad(args):
    from retico.agent.hearing import Hearing
    from retico.agent.speech import Speech
    from retico.agent.eot_vad import EOT_VAD

    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        use_asr=args.use_asr,
        record=args.record,
        debug=False,
    )
    speech = Speech(
        chunk_time=0.05, sample_rate=16000, bytes_per_sample=2, tts_client="amazon"
    )
    eot_vad = EOT_VAD(chunk_time=args.chunk_time)
    nlg = NLGSimple()
    turn_taking = TurnTaking(debug=args.debug)

    # Connect Components
    hearing.vad.subscribe(eot_vad)
    eot_vad.subscribe(turn_taking)
    turn_taking.subscribe(nlg)
    nlg.subscribe(speech.tts)
    speech.audio_dispatcher.subscribe(turn_taking)

    # RUN
    hearing.run_components()
    speech.run_components()
    eot_vad.run()
    nlg.run()
    turn_taking.run()
    try:
        input()
    except KeyboardInterrupt:
        pass
    hearing.stop_components()
    speech.stop_components()
    eot_vad.stop()
    nlg.stop()


def test_turntaking_asr_final(args):
    from retico.agent.hearing import Hearing
    from retico.agent.speech import Speech
    from retico.agent.eot_asr import EOT_ASR_FINAL

    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        use_asr=True,
        record=args.record,
        debug=False,
    )
    speech = Speech(
        chunk_time=0.05, sample_rate=16000, bytes_per_sample=2, tts_client="amazon"
    )
    eot_asr_final = EOT_ASR_FINAL(chunk_time=args.chunk_time)
    nlg = NLGSimple()
    turn_taking = TurnTaking(debug=args.debug)

    # Connect Components
    hearing.asr.subscribe(eot_asr_final)
    eot_asr_final.subscribe(turn_taking)
    turn_taking.subscribe(nlg)
    nlg.subscribe(turn_taking)
    nlg.subscribe(speech.tts)
    speech.audio_dispatcher.subscribe(turn_taking)

    # RUN
    hearing.run_components()
    speech.run_components()
    eot_asr_final.run()
    nlg.run()
    turn_taking.run()
    try:
        input()
    except KeyboardInterrupt:
        pass
    hearing.stop_components()
    speech.stop_components()
    eot_asr_final.stop()
    nlg.stop()


def test_turntaking_lm_final(args):
    from retico.agent.hearing import Hearing
    from retico.agent.speech import Speech
    from retico.agent.eot_asr import EOT_LM_Final, EOT_ASR_DEBUG

    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        use_asr=True,
        record=args.record,
        debug=False,
    )
    speech = Speech(
        chunk_time=0.05, sample_rate=16000, bytes_per_sample=2, tts_client="amazon"
    )
    eot_lm_final = EOT_LM_Final()
    eot_lm_debug = EOT_ASR_DEBUG()
    nlg = NLGSimple()
    turn_taking = TurnTaking(debug=args.debug)

    # Connect Components
    hearing.asr.subscribe(eot_lm_final)
    eot_lm_final.subscribe(turn_taking)
    eot_lm_final.subscribe(eot_lm_debug)
    turn_taking.subscribe(nlg)
    nlg.subscribe(turn_taking)
    nlg.subscribe(speech.tts)
    speech.audio_dispatcher.subscribe(turn_taking)

    # RUN
    hearing.run_components()
    speech.run_components()
    eot_lm_final.run()
    eot_lm_debug.run()
    nlg.run()
    turn_taking.run()
    try:
        input()
    except KeyboardInterrupt:
        pass
    hearing.stop_components()
    speech.stop_components()
    eot_lm_final.stop()
    eot_lm_debug.stop()
    nlg.stop()


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("--chunk_time", type=float, default=0.01)
    parser.add_argument("--sample_rate", type=int, default=16000)
    parser.add_argument("--bytes_per_sample", type=int, default=2)
    parser.add_argument("--use_asr", action="store_true")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--module", type=str)

    args = parser.parse_args()

    if args.module == "vad":
        test_turntaking_vad(args)
    elif args.module == "asr":
        test_turntaking_asr_final(args)
    elif args.module == "lm_final":
        test_turntaking_lm_final(args)
