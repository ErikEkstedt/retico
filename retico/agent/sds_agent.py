from retico.agent.hearing import Hearing
from retico.agent.speech import Speech
from retico.agent.turn_taking import TurnTaking


class SDSAgent(object):
    def __init__(self):

        self.hearing = Hearing()
        self.speech = Speech()
        self.turn_taking = TurnTaking()
