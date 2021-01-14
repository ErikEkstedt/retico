from retico.core.abstract import (
    AbstractModule,
    AbstractConsumingModule,
    IncrementalUnit,
)

from retico.agent.common import EotIU, VadIU
from retico.agent.utils import Color as C

import numpy as np

"""
Subscribe to a VAD-module and smoothes out the signal and outputs eot-unit when it is triggered
"""


class EOT_VAD_DEBUG(AbstractConsumingModule):
    @staticmethod
    def input_ius():
        return [EotIU]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_eot_state = False

    def process_iu(self, input_iu):
        if input_iu != self.last_eot_state:
            color = C.red
            if input_iu.eot:
                color = C.green

            s = color + "EOT VAD DEBUG"
            s += "\nEOT:  " + str(input_iu.eot)
            s += "\nProb: " + str(input_iu.probability)
            print(s + C.end)
            self.last_eot_state = input_iu.eot


class EOT_VAD(AbstractModule):
    @staticmethod
    def name():
        return "EOT-VAD Module"

    @staticmethod
    def description():
        return "EOT based on vad_threshold"

    @staticmethod
    def input_ius():
        return [VadIU]

    @staticmethod
    def output_iu():
        return EotIU

    def __init__(
        self, chunk_time, vad_off_time=0.75, vad_on_time=0.4, prob_thresh=0.9, **kwargs
    ):
        super().__init__(**kwargs)
        self.chunk_time = chunk_time
        self.eot_state = True

        self.prob_thresh = prob_thresh

        # Off used to de-activate the user state
        self.vad_off_time = vad_off_time
        n_off = int(vad_off_time / chunk_time)
        self.vad_off_context = np.zeros(n_off)

        # On used to activate the user state
        self.vad_on_time = vad_on_time
        n_on = int(vad_on_time / chunk_time)
        self.vad_on_context = np.zeros(n_on)

    def add_state(self, is_speaking):
        is_silent = (not is_speaking) * 1.0
        is_speaking *= 1.0

        self.vad_on_context = np.concatenate(
            (self.vad_on_context[1:], np.array((is_speaking,)))
        )
        self.vad_off_context = np.concatenate(
            (self.vad_off_context[1:], np.array((is_silent,)))
        )

    def output(self):
        output_iu = self.create_iu()
        output_iu.set_eot(self.probability, self.eot_state)
        return output_iu

    def process_iu(self, input_iu):
        self.add_state(input_iu.is_speaking)
        if self.eot_state:
            if self.vad_on_context.mean() >= self.prob_thresh:
                self.eot_state = False
                self.probability = self.vad_on_context.mean()
                return self.output()
        else:
            if self.vad_off_context.mean() >= self.prob_thresh:
                self.eot_state = True
                self.probability = self.vad_off_context.mean()
                return self.output()


def test_eot_vad():
    from retico.agent.hearing import Hearing

    sample_rate = 16000
    chunk_time = 0.01
    bytes_per_sample = 2

    hearing = Hearing(
        chunk_time=chunk_time,
        sample_rate=sample_rate,
        bytes_per_sample=bytes_per_sample,
        use_asr=False,
        record=False,
        debug=False,
    )
    eot_vad = EOT_VAD(chunk_time=chunk_time)
    eot_vad_debug = EOT_VAD_DEBUG()

    # Connect Components
    hearing.vad.subscribe(eot_vad)
    eot_vad.subscribe(eot_vad_debug)

    # run
    hearing.run_components()
    eot_vad.run()
    eot_vad_debug.run()
    try:
        input()
    except KeyboardInterrupt:
        pass
    hearing.stop_components()
    eot_vad.stop()
    eot_vad_debug.stop()


if __name__ == "__main__":
    test_eot_vad()
