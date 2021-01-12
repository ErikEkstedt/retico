import requests
import json

from retico.core.abstract import AbstractModule, IncrementalUnit
from retico.core.text.common import SpeechRecognitionIU

from retico.agent.vad import VadIU

URL_TRP = "http://localhost:5000/trp"

"""
EOT module

This module determines whether the 'other' agent is done with their turn or not.

It relies on the ASR- and VAD-modules to make the decision.

The vad is used to check that the user has been silent for more than `self.vad_time_min`.

The asr is used to infer if the asr is 'final' meaning that the asr engine thought the utterance was done.

NOTES:

    * We need the entire history of the conversation to use TurnGPT as we'd like. So perhaps this is just a main part of
    the turntaking module.

"""


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
        return [SpeechRecognitionIU, VadIU]

    @staticmethod
    def output_iu():
        return EndOfTurnIU

    def __init__(
        self, bc_trp_thresh_min=0.1, bc_trp_thresh_max=0.4, vad_time_min=0.2, **kwargs
    ):
        super().__init__(**kwargs)
        self.bc_trp_thresh_min = bc_trp_thresh_min
        self.bc_trp_thresh_max = bc_trp_thresh_max
        self.vad_time_min = vad_time_min

    def get_trp(self, text):
        json_data = {"text": text}
        response = requests.post(URL_TRP, json=json_data)
        d = json.loads(response.content.decode())
        return d["trp"]

    def handle_vad(self, input_iu):
        if input_iu.is_speaking == False:
            if input_iu.silence_time > self.vad_time_min:
                self.vad_time_clear = True
                # print("BC-VAD-time: ", True)
        else:
            self.vad_time_clear = False

    def handle_asr(self, input_iu):
        if not input_iu.final:
            trp = self.get_eot(input_iu.text)
            if self.bc_trp_thresh_min <= trp <= self.bc_trp_thresh_max:
                self.trp_clear = True
            else:
                self.trp_clear = False
        else:
            self.trp_clear = False

        self.speak()

    def process_iu(self, input_iu):
        if isinstance(input_iu, SpeechRecognitionIU):
            self.handle_asr(input_iu)
        elif isinstance(input_iu, VadIU):
            self.handle_vad(input_iu)

        if input_iu.text == "":
            print("empty input")
        self.current_utterance += " " + input_iu.text.strip()
        # self.current_utterance = re.sub("\s\s+", "", self.current_utterance.strip())
        probability = self.get_trp(self.current_utterance)

        print(f"EOT: {self.current_utterance} = {round(probability, 3)*100}%")
        if input_iu.committed:
            self.current_utterance = ""

        output_iu = self.create_iu()
        output_iu.probability = probability
        return output_iu


def test_eot():
    pass


if __name__ == "__main__":
    test_eot()
