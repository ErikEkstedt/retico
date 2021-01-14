from retico.agent.common import VadIU, SadIU
from retico.core.abstract import AbstractModule, AbstractConsumingModule

from retico.agent.utils import Color as C

import numpy as np


class SADModuleDEBUG(AbstractConsumingModule):
    @staticmethod
    def name():
        return "VAD Debug Module"

    @staticmethod
    def description():
        return "VAD Debug"

    @staticmethod
    def input_ius():
        return [SadIU]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_is_speaking = True

    def process_iu(self, input_iu):
        if input_iu.is_speaking != self.last_is_speaking:
            self.last_is_speaking = input_iu.is_speaking
            if input_iu.is_speaking:
                print(C.green + "SAD DEBUG")
                print("\tis_speaking: ", input_iu.is_speaking)
                print(C.end)
            else:
                print(C.red + "SAD DEBUG")
                print("\tis_speaking: ", input_iu.is_speaking)
                print(C.end)


class SADModule(AbstractModule):
    @staticmethod
    def name():
        return "SAD Module"

    @staticmethod
    def description():
        return "Speech Activity based on vad_threshold"

    @staticmethod
    def input_ius():
        return [VadIU]

    @staticmethod
    def output_iu():
        return SadIU

    def __init__(
        self, chunk_time, vad_off_time=0.5, vad_on_time=0.2, prob_thresh=0.9, **kwargs
    ):
        super().__init__(**kwargs)
        self.started = False
        self.is_speaking = False
        self.probability = 0

        self.chunk_time = chunk_time
        self.prob_thresh = prob_thresh

        # Used to turn OFF speech activity
        self.vad_off_time = vad_off_time
        n_off = int(vad_off_time / chunk_time)
        self.vad_off_context = np.zeros(n_off)

        # Used to turn ON speech activity
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
        output_iu.is_speaking = self.is_speaking
        output_iu.probability = self.probability
        return output_iu

    def process_iu(self, input_iu):
        if not self.started:
            self.started = True
            self.is_speaking = input_iu.is_speaking
            self.probability = self.vad_off_context.mean()
            return self.output()
        self.add_state(input_iu.is_speaking)
        if self.is_speaking:
            if self.vad_off_context.mean() >= self.prob_thresh:
                self.is_speaking = False
                self.probability = self.vad_off_context.mean()
                return self.output()
        else:
            if self.vad_on_context.mean() >= self.prob_thresh:
                self.is_speaking = True
                self.probability = self.vad_on_context.mean()
                return self.output()


def test_sad():
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
    eot_vad = SADModule(chunk_time=chunk_time)
    eot_vad_debug = SADModuleDEBUG()

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
    test_sad()
