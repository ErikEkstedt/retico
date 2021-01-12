import time
import threading
import requests
import json
import re
import random

from retico.core.abstract import AbstractModule, AbstractConsumingModule
from retico.core.audio.common import DispatchedAudioIU
from retico.core.text.common import SpeechRecognitionIU, GeneratedTextIU

# from retico.core.text.asr import TextDispatcherModule

from retico.agent.hearing import Hearing
from retico.agent.speech import Speech, TTSDummy
from retico.agent.vad import VadIU
from retico.agent.backchannel import BackChannelModule
from retico.agent.utils import Color as C


"""
The agent that is actually conducting a conversation.

The starting point is the repeat agent which listens, and remember, what is being said and upon finality from the ASR
starts repeating what was said.

1. Make the agent pause what it is saying if the user starts talking during the utterance
2. Make the agent interrupt the user if they talk for say longer than 2 seconds


Create a simple REST-server for TurnGPT. That can return either simply the TRP for each word recieved along with the
most likely word. Or to actually project in the future and return the most likely future (rank).
"""

URL_SAMPLE = "http://localhost:5000/sample"
URL_EOT = "http://localhost:5000/eot"
URL_TRP = "http://localhost:5000/trp"


def get_sampled_response(text):
    # json_data = {"text": ["Hello there, how can I help you?", "I want to eat food."]}
    json_data = {"text": text}
    response = requests.post(URL_SAMPLE, json=json_data)
    d = json.loads(response.content.decode())
    return d["response"]


def get_eot(text):
    # json_data = {"text": ["Hello there, how can I help you?", "I want to eat food."]}
    json_data = {"text": text}
    response = requests.post(URL_EOT, json=json_data)
    d = json.loads(response.content.decode())
    return d["eot"]


class SpeakerState:
    def __init__(self):
        """Create a new SpeakerState with the default parameters

        Returns:
            type: Description of returned object.

        """
        self.utter_start = 0
        self.utter_end = 0
        self.dialogue_started = False
        self.is_active = False
        self.completion = 0.0

    def __repr__(self):
        rep = ""
        rep += "utter_start: %f\n" % self.utter_start
        rep += "utter_end: %f\n" % self.utter_end
        rep += "dialogue_started: %s\n" % self.dialogue_started
        rep += "is_active: %s\n" % self.is_active
        rep += "completion: %s\n" % self.completion
        return rep

    @property
    def turn_duration(self):
        """Return the time since the current utterance started.

        Returns:
            flaot: The time since the current utterance started.

        """
        return time.time() - self.utter_start

    @property
    def since_last_turn(self):
        """Return the time since the last utterance ended.

        Returns:
            float: The time since the last utterance ended.

        """
        return time.time() - self.utter_end


class HistoryTracker:
    def __init__(self):
        self.turns = []
        self.speakers = []

    def reset(self):
        self.turns = []
        self.speakers = []

    def add_turn_utterance(self, text, speaker):
        self.turns.append(text)
        self.speakers.append(speaker)

    def __repr__(self):
        s = "History"
        for turn, speaker in zip(self.turns, self.speakers):
            if speaker == "me":
                s += "\nMe: " + turn
            else:
                s += "\n\t\tOther: " + turn
        return s

    def __len__(self):
        return len(self.turns)

    def get_turns(self):
        return self.turns.copy()


class TurnTakingBase(AbstractModule):
    SLEEP_TIME = 0.05
    EVENT_SILENCE = "silence"

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU, DispatchedAudioIU, VadIU]

    @staticmethod
    def output_iu():
        return GeneratedTextIU

    def setup(self):
        """Sets the dialogue_finished flag to false. This may be overwritten
        by a class to setup the dialogue manager."""
        self.dialogue_finished = False

    def prepare_run(self):
        """Prepares the dialogue_loop and the DialogueState of the agent and the
        interlocutor by resetting the timers.
        This method starts the dialogue_loop."""
        self.reset_states()
        t = threading.Thread(target=self.dialogue_loop)
        t.start()

    def reset_states(self):
        """Reset the timers for self and the interlocutor.

        This method is used in the begining of the dialogue to avoid strange
        behavior when no utterance has preceeded.
        """
        now = time.time()
        self.me.utter_start = now
        self.me.utter_end = now
        self.other.utter_start = now
        self.other.utter_end = now
        self.history.reset()
        self.dialogue_started = False
        self.dialogue_finished = False

    def shutdown(self):
        """Sets the dialogue_finished flag that eventually terminates the
        dialogue_loop."""
        self.dialogue_finished = True

    @property
    def both_speak(self):
        """Whether both agents are currently speaking..

        Returns:
            bool: Whether both agents are currently speaking
        """
        return self.me.is_active and self.other.is_active

    @property
    def both_silent(self):
        """Whether both agents are currently not speaking

        Returns:
            bool: Whether both agents are currently not speaking
        """
        return not self.me.is_active and not self.other.is_active

    @property
    def only_i_speak(self):
        """Whether this agent is speaking and the interlocutor is silent

        Returns:
            bool: Whether this agent is speaking and the interlocutor is silent
        """
        return self.me.is_active and not self.other.is_active

    @property
    def only_they_speak(self):
        """Whether the interlocutor is speaking and this agent is silent

        Returns:
            bool: Whether the interlocutor is speaking and this agent is silent
        """
        return not self.me.is_active and self.other.is_active

    def generate_response(self):
        json_data = {"text": self.history.get_turns()}
        response = requests.post(URL_SAMPLE, json=json_data)
        d = json.loads(response.content.decode())
        self.next_response = d["response"]

    def listen_self(self, input_iu):
        """Handles the state of the agents own dispatched audio.

        This method sets the utter_end and utter_start flag of the DialogueState
        object that corresponds to its own state.
        After an IU is recieved that changes the iterlocutor own state (to
        speaking or silent), the suspend flag is set to False so that the
        dialogue loop may continue handling the current dialogue state.

        Args:
            input_iu (DispatchedAudioIU): The dispatched audio IU of the agents
                AudioDispatcherModule.
        """
        if self.me.is_active and not input_iu.is_dispatching:
            self.me.utter_end = time.time()
            self.me.last_act = self.me.current_act
            self.me.current_act = None
            self.suspended = False
        elif not self.me.is_active and input_iu.is_dispatching:
            self.me.utter_start = time.time()
            self.suspended = False
        self.me.is_active = input_iu.is_dispatching
        self.me.completion = input_iu.completion

    def start_speaking(self):
        """
        Adds our planned utterances to the dialog state and pass IU to the TTS
        """
        self.history.add_turn_utterance(self.next_response, speaker="me")
        output_iu = self.create_iu(None)
        output_iu.payload = self.next_response
        output_iu.dispatch = True
        self.append(output_iu)

    def silence(self):
        output_iu = self.create_iu(None)
        output_iu.payload = ""
        output_iu.dispatched = False
        self.append(output_iu)
        self.event_call(self.EVENT_SILENCE)
        self.suspended = True

    def dialogue_loop(self):
        """
        The dialogue loop that continuously checks the state of the agent and
        the interlocutor to determine what action to perform next.
        """
        last_state = -1
        while not self.dialogue_finished:
            # Suspend execution until something happens
            while self.suspended:
                time.sleep(self.SLEEP_TIME)

            if not self.dialogue_started and self.first_utterance:
                self.reset_states()
                self.next_response = self.initial_utterance
                self.start_speaking()
                self.dialogue_started = True

            if self.both_silent:
                # 0
                if last_state != 0:
                    print(C.yellow + "Agent: BOTH silent" + C.end)
                    last_state = 0
            elif self.only_i_speak:
                # 1
                if last_state != 1:
                    print(C.blue + "Agent: only I speak" + C.end)
                    last_state = 1
            elif self.only_they_speak:
                # 2
                if last_state != 2:
                    print(C.cyan + "Agent: only THEY speak" + C.end)
                    last_state = 2
            elif self.both_speak:
                if last_state != 3:
                    print(C.pink + "BOTH SPEAK" + C.end)
                    last_state = 3
                self.silence()

            time.sleep(self.SLEEP_TIME)


class TurnTakingModule(TurnTakingBase):
    @staticmethod
    def name():
        return "Turn Taking DM Module"

    @staticmethod
    def description():
        return "A dialogue manager that uses eot predictions for turn taking"

    def __init__(self, first_utterance=True, **kwargs):
        """Initializes the class with the flag of wether the agent should start
        the conversation or wait until the interlocutor starts the conversation.

        Args:
            first_utterance (bool): Whether this agent starts the conversation
        """
        super().__init__(**kwargs)
        self.first_utterance = first_utterance
        self.dialogue_finished = False
        self.dialogue_started = False
        self.bc_silence_time = 0.1

        self.history = HistoryTracker()
        self.me = SpeakerState()
        self.other = SpeakerState()
        self.current_utterance = ""  # stored utterance if we do not which to take the turn even with asr.final=True

        # EOT/turn-taking
        self.eot_prob_min = 0.1

        self.initial_utterance = "Hello there, how can I help you?"
        self.suspended = False

    def process_iu(self, input_iu):
        if isinstance(input_iu, SpeechRecognitionIU):
            self.listen_other(input_iu)
        elif isinstance(input_iu, VadIU):
            self.handle_vad(input_iu)
        elif isinstance(input_iu, DispatchedAudioIU):
            self.listen_self(input_iu)
        return None

    def handle_vad(self, input_iu):
        if self.other.is_active and not input_iu.is_speaking:
            if input_iu.silence_time > 0.2:
                self.other.is_active = False
        elif not self.other.is_active and input_iu.is_speaking:
            self.other.is_active = True

    def listen_other(self, input_iu):
        """
        Listening to the other interlocutor and estimate if they are done or not.
        """
        if input_iu.final:
            # Abort the user says goodbye
            if "goodbye" in input_iu.text or "bye" in input_iu.text:
                self.next_response = "Goodbye."
                self.start_speaking()
                self.shutdown()
            else:
                prel_current_utterance = " ".join(
                    [self.current_utterance, input_iu.text]
                )

                # Add preliminary utterance to history
                preliminary_turns = self.history.get_turns()
                preliminary_turns.append(prel_current_utterance)
                trp = self.get_eot(preliminary_turns)  # estimate eot prob

                # if the asr is final and our trp-model puts a high enought likelihood of turn-shift we decide that it is a
                # turn-shift. We add the previous utterance to the history and generate a response.
                if self.eot_prob_min <= trp:
                    print(C.green + f"EOT recognized TRP: {trp}" + C.end)
                    self.history.add_turn_utterance(
                        prel_current_utterance, speaker="other"
                    )
                    self.current_utterance = ""  # reset current_utterance
                    self.generate_response()
                    self.start_speaking()
                else:
                    print(C.red + f"Listening TRP: {trp}" + C.end)
                    self.current_utterance = prel_current_utterance
                    print("current: ", self.current_utterance)

    def get_eot(self, text):
        json_data = {"text": text}
        response = requests.post(URL_TRP, json=json_data)
        d = json.loads(response.content.decode())
        return d["trp"][-1]  # only care about last token


class SimpleTurnTakingModule(TurnTakingBase):
    @staticmethod
    def name():
        return "Turn Taking DM Module"

    @staticmethod
    def description():
        return "A dialogue manager that uses eot predictions for turn taking"

    def __init__(self, first_utterance=True, **kwargs):
        """Initializes the class with the flag of wether the agent should start
        the conversation or wait until the interlocutor starts the conversation.

        Args:
            first_utterance (bool): Whether this agent starts the conversation
        """
        super().__init__(**kwargs)
        self.first_utterance = first_utterance
        self.dialogue_finished = False
        self.dialogue_started = False
        self.bc_silence_time = 0.1

        self.history = HistoryTracker()
        self.me = SpeakerState()
        self.other = SpeakerState()
        self.current_utterance = ""  # stored utterance if we do not which to take the turn even with asr.final=True

        # EOT/turn-taking
        self.eot_prob_min = 0.1

        self.initial_utterance = "Hello there, how can I help you?"
        self.suspended = False

    def process_iu(self, input_iu):
        if isinstance(input_iu, SpeechRecognitionIU):
            self.listen_other(input_iu)
        elif isinstance(input_iu, VadIU):
            self.handle_vad(input_iu)
        elif isinstance(input_iu, DispatchedAudioIU):
            self.listen_self(input_iu)
        return None

    def handle_vad(self, input_iu):
        if self.other.is_active and not input_iu.is_speaking:
            if input_iu.silence_time > 0.2:
                self.other.is_active = False
        elif not self.other.is_active and input_iu.is_speaking:
            self.other.is_active = True

    def listen_other(self, input_iu):
        """
        Listening to the other interlocutor and estimate if they are done or not.
        """
        if input_iu.final:
            # Abort the user says goodbye
            if "goodbye" in input_iu.text or "bye" in input_iu.text:
                self.next_response = "Goodbye."
                self.start_speaking()
                self.shutdown()
            else:
                self.history.add_turn_utterance(input_iu.text, speaker="other")
                print(C.green + f"Final" + C.end)
                self.generate_response()
                self.start_speaking()

    def get_eot(self, text):
        json_data = {"text": text}
        response = requests.post(URL_TRP, json=json_data)
        d = json.loads(response.content.decode())
        return d["trp"][-1]  # only care about last token


class Agent(object):
    def __init__(
        self,
        chunk_time=0.01,
        sample_rate=16000,
        bytes_per_sample=2,
        speech_chunk_time=0.1,
        use_backchannel_module=False,
        simple=False,
    ):
        self.chunk_time = chunk_time
        self.sample_rate = sample_rate
        self.bytes_per_sample = bytes_per_sample
        self.speech_chunk_time = speech_chunk_time
        self.use_backchannel_module = use_backchannel_module
        self.simple = simple

        # Percecption/Senses
        self.hearing = Hearing(chunk_time, sample_rate, bytes_per_sample, debug=False)
        self.speech = Speech(
            speech_chunk_time, sample_rate, bytes_per_sample, tts_client="amazon"
        )
        if self.simple:
            self.turn_taking = SimpleTurnTakingModule(first_utterance=True)
        else:
            self.turn_taking = TurnTakingModule(first_utterance=True)
        if use_backchannel_module:
            self.bc = BackChannelModule(
                cooldown=2.0,
                bc_trp_thresh_min=0.1,
                bc_trp_thresh_max=0.4,
                vad_time_min=0.1,
            )

        self.connect_components()

    def connect_components(self):
        self.hearing.connect_components()
        if self.use_backchannel_module:
            self.hearing.vad.subscribe(self.bc)
            self.hearing.asr.subscribe(self.bc)

        self.hearing.asr.subscribe(self.turn_taking)  # EOT estimation
        self.hearing.vad.subscribe(self.turn_taking)  # EOT estimation
        self.turn_taking.subscribe(self.speech.tts)  # speak
        self.speech.audio_dispatcher.subscribe(self.turn_taking)  # listen_self

    def run(self):
        self.hearing.run_components()
        self.speech.run_components()
        if self.use_backchannel_module:
            self.bc.run()
        self.turn_taking.setup()
        self.turn_taking.prepare_run()
        self.turn_taking.run()

    def stop(self):
        self.hearing.stop_components()
        self.speech.stop_components()
        if self.use_backchannel_module:
            self.bc.stop()
        self.turn_taking.stop()


def run_agent(simple=False):
    agent = Agent(use_backchannel_module=True, simple=simple)
    agent.run()
    input()
    agent.stop()


def test_components():
    sample_rate = 16000
    chunk_time = 0.01
    bytes_per_sample = 2
    print("sample_rate: ", sample_rate)
    print("chunk_time: ", chunk_time)
    print("bytes_per_sample: ", bytes_per_sample)

    hearing = Hearing(chunk_time, sample_rate, bytes_per_sample, debug=False)
    bc = BackChannelModule(
        cooldown=2.0, bc_trp_thresh_min=0.1, bc_trp_thresh_max=0.4, vad_time_min=0.1
    )

    # speech = Speech(0.1, sample_rate, bytes_per_sample, tts_client="amazon")
    # speech = TTSDummy()
    # agent = TurnTakingAgent()

    # Connect Components
    hearing.connect_components()

    # Connect bc to hearing
    hearing.vad.subscribe(bc)
    hearing.asr.subscribe(bc)

    # Run
    hearing.run_components()
    bc.run()

    input()

    hearing.stop_components()
    bc.stop()


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("--simple", action="store_true")
    args = parser.parse_args()
    if args.simple:
        print("Using Baseline ASR TurnTaking")
    else:
        print("Using ASR + TurnGPT TurnTaking")

    run_agent(simple=args.simple)
    # run_agent(simple=True)
    # test_components()

    # Some tests?

    # Bot
    "hello there how can I help you today?"

    # me
    "hi there"  # pause
    "I would like to book a flight"

    "I would like to fly to"  # pause
    "paris"

    "let's see"  # pause
    "hmm next weekend please"
    # Bot answer not deterministic
