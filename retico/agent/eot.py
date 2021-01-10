import requests
import json

from retico.core.abstract import AbstractModule, IncrementalUnit
from retico.core.text.common import SpeechRecognitionIU


URL_EOT = "http://localhost:5000/eot"


def get_eot(text):
    # json_data = {"text": ["Hello there, how can I help you?", "I want to eat food."]}
    json_data = {"text": text}
    response = requests.post(URL_EOT, json=json_data)
    d = json.loads(response.content.decode())
    return d["eot"]


class EndOfTurnIU(IncrementalUnit):
    """An incremental unit used for prediction of the end of the turn. This
    information may be used by a dialogue management module to plan next turns
    and enabling realistic turn taking.
    """

    @staticmethod
    def type():
        return "End-of-Turn Incremental Unit"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.probability = 0.0
        self.is_speaking = False

    def set_eot(self, probability=0.0, is_speaking=False):
        """Set the end-of-turn probability and a flag if the interlocutor is
        currently speaking (VAD).

        Args:
            probability (float): The probability that the turn is ending.
            is_speaking (bool): Whether or not the interlocutor is speaking.
        """
        self.is_speaking = is_speaking
        self.probability = probability


# TODO
class EOTModule(AbstractModule):
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_utterance = ""
        self.turns = []

    def process_iu(self, input_iu):
        if input_iu.text == "":
            print("empty input")
        self.current_utterance += " " + input_iu.text.strip()
        # self.current_utterance = re.sub("\s\s+", "", self.current_utterance.strip())
        probability = get_eot(self.current_utterance)

        print(f"EOT: {self.current_utterance} = {round(probability, 3)*100}%")
        if input_iu.committed:
            self.current_utterance = ""

        output_iu = self.create_iu()
        output_iu.probability = probability
        return output_iu
