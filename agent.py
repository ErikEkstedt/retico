import time
import threading
import requests
import json

from retico.core.abstract import AbstractModule, IncrementalUnit
from retico.core.audio.common import DispatchedAudioIU
from retico.core.text.common import SpeechRecognitionIU, GeneratedTextIU
from retico.core.text.asr import TextDispatcherModule
from retico.core.prosody.common import EndOfTurnIU

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
        return self.turns


# TODO
class EOT(AbstractModule):
    @staticmethod
    def name():
        return "EOT Turn Taking Module"

    @staticmethod
    def description():
        return "A module which incrementally estimates the EOT probality"

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU]

    @staticmethod
    def output_iu():
        return EndOfTurnIU


class BaseAgent(AbstractModule):
    SLEEP_TIME = 0.05
    EVENT_SILENCE = "silence"

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


class TurnTakingAgent(BaseAgent):
    @staticmethod
    def name():
        return "Turn Taking DM Module"

    @staticmethod
    def description():
        return "A dialogue manager that uses eot predictions for turn taking"

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU, DispatchedAudioIU]

    @staticmethod
    def output_iu():
        return GeneratedTextIU

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

        # Starting with a repeater
        self.dialogue_manager = TextDispatcherModule()

        self.history = HistoryTracker()
        self.me = SpeakerState()
        self.other = SpeakerState()

        self.initial_utterance = "Hello there, how can I help you?"
        self.current_question_ind = 0
        self.suspended = False

    def reset_utterance_timers(self):
        """Reset the timers for self and the interlocutor.

        This method is used in the begining of the dialogue to avoid strange
        behavior when no utterance has preceeded.
        """
        now = time.time()
        self.me.utter_start = now
        self.me.utter_end = now
        self.other.utter_start = now
        self.other.utter_end = now

    def process_iu(self, input_iu):
        if isinstance(input_iu, SpeechRecognitionIU):
            self.listen(input_iu)
        elif isinstance(input_iu, DispatchedAudioIU):
            self.self_observe(input_iu)
        return None

    def listen(self, input_iu):
        if input_iu.final:
            self.history.add_turn_utterance(input_iu.text, speaker="other")
            if "goodbye" in input_iu.text:
                self.next_response = "Goodbye."
                self.shutdown()
            else:
                self.next_response = get_sampled_response(text=self.history.get_turns())
            self.speak()
        return None

    def start_speaking(self):
        output_iu = self.create_iu(None)
        output_iu.payload = self.next_response
        output_iu.dispatch = True
        self.append(output_iu)
        self.history.add_turn_utterance(self.next_response, speaker="me")
        print(self.history)

    def speak(self):
        if not self.dialogue_started:
            # Start of dialogue
            self.next_response = self.initial_utterance
            self.start_speaking()
        else:
            self.start_speaking()

    def self_observe(self, input_iu):
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
        print("Agent self_observe")
        if self.me.is_active and not input_iu.is_dispatching:
            self.me.utter_end = time.time()
            self.me.last_act = self.me.current_act
            self.me.current_act = None
            self.suspended = False
        elif not self.me.is_active and input_iu.is_dispatching:
            self.me.utter_start = time.time()
            self.suspended = False
            self.reset_random()
        self.me.is_active = input_iu.is_dispatching
        self.me.completion = input_iu.completion

    def silence(self):
        output_iu = self.create_iu(None)
        output_iu.payload = ""
        output_iu.dispatched = False
        self.append(output_iu)
        self.event_call(self.EVENT_SILENCE)
        self.suspended = True

    def dialogue_loop(self):
        """The dialogue loop that continuously checks the state of the agent and
        the interlocutor to determine what action to perform next.

        The dialogue loop is suspended when the agent starts speaking until the
        agent recieves DispatchedAudioIU from itself and registeres that the
        speech is being produced.

        During the loop, the agent checks the spaking states of both themself
        and their interlocutor to determin whether or not they should interrupt,
        take over the turn, continue their own turn or prevent double talk.

        When two agents are interacting the pause-model of the one agent and the
        gando-model of the other agent determine if a turn is passed over or if
        the agent continues speaking.
        """
        while not self.dialogue_finished:
            # Suspend execution until something happens
            while self.suspended:
                time.sleep(self.SLEEP_TIME)

            if not self.dialogue_started:
                if self.first_utterance:
                    self.reset_utterance_timers()
                    self.speak()
                    self.dialogue_started = True
                continue

            if self.only_i_speak:
                # print("Agent: only I speak")
                pass  # Do nothing.
            elif self.only_they_speak:
                # print("Agent: only THEY speak")
                pass  # Do nothing.
            elif self.both_silent:
                # print("Agent: BOTH silent")
                pass  # Do nothing.
            elif self.both_speak:
                self.silence()

            time.sleep(self.SLEEP_TIME)

    def setup(self):
        """Sets the dialogue_finished flag to false. This may be overwritten
        by a class to setup the dialogue manager."""
        self.dialogue_finished = False

    def prepare_run(self):
        """Prepares the dialogue_loop and the DialogueState of the agent and the
        interlocutor by resetting the timers.
        This method starts the dialogue_loop."""
        self.reset_utterance_timers()
        t = threading.Thread(target=self.dialogue_loop)
        t.start()

    def shutdown(self):
        """Sets the dialogue_finished flag that eventually terminates the
        dialogue_loop."""
        self.dialogue_finished = True


def run_agent():
    from perception import Hearing, Speech

    sample_rate = 16000
    chunk_time = 0.05
    bytes_per_sample = 2
    print("sample_rate: ", sample_rate)
    print("chunk_time: ", chunk_time)
    print("bytes_per_sample: ", bytes_per_sample)

    hearing = Hearing(chunk_time, sample_rate, bytes_per_sample, debug=False)
    speech = Speech(chunk_time, sample_rate, bytes_per_sample, tts_client="amazon")
    agent = TurnTakingAgent()

    hearing.connect_components()
    hearing.asr.subscribe(agent)
    agent.subscribe(speech.tts)
    speech.connect_components()

    hearing.run_components()
    agent.dialogue_manager.run()
    speech.run_components()

    agent.setup()
    agent.prepare_run()  #  starts a thread and the dialogue loop
    agent.run()

    input()

    hearing.stop_components()
    agent.dialogue_manager.stop()
    speech.stop_components()


if __name__ == "__main__":
    run_agent()
