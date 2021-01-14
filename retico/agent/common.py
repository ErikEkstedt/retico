import time

from retico.core.abstract import IncrementalUnit


class VadIU(IncrementalUnit):
    @staticmethod
    def type():
        return "Vad IU"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_speaking = False
        self.silence_time = 0

    def set_is_speaking(self):
        self.is_speaking = True

    def set_silence_time(self, silence_time):
        self.silence_time = silence_time


class SadIU(IncrementalUnit):
    @staticmethod
    def type():
        return "Speech activity IU"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_speaking = False
        self.silence_time = 0


class TurnTakingIU(IncrementalUnit):
    """An incremental unit used for prediction of the end of the turn. This
    information may be used by a dialogue management module to plan next turns
    and enabling realistic turn taking.
    """

    ACTIONS = ["speak", "silence", "listen", "interrupt", "backchannel"]

    @staticmethod
    def type():
        return "TurnTaking Incremental Unit"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.action = "None"
        self.dialogue_end = False
        self.meta_data = {}

    def set_action(self, action, meta_data=None):
        """Set the end-of-turn probability and a flag if the interlocutor is
        currently speaking (VAD).

        Args:
            probability (float): The probability that the turn is ending.
            is_speaking (bool): Whether or not the interlocutor is speaking.
        """
        assert (
            action in self.ACTIONS
        ), f"TurnTakingIU: Must provide an action in {self.ACTIONS}. Error: {action}"
        self.action = action
        self.time = time.time()
        if meta_data is not None:
            self.meta_data = meta_data


class EotIU(IncrementalUnit):
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
        self.eot = False
        self.text = ""

    def set_eot(self, probability=0.0, eot=False, text="", meta_data={}):
        """Set the end-of-turn probability and a flag if the interlocutor is
        currently speaking (VAD).

        Args:
            probability (float): The probability that the turn is ending.
            is_speaking (bool): Whether or not the interlocutor is speaking.
        """
        self.eot = eot
        self.probability = probability
        self.text = text
        self.meta_data = meta_data
