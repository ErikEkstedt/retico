from retico.core.abstract import (
    AbstractModule,
    AbstractConsumingModule,
)
from retico.core.audio.common import AudioIU
from retico.agent.common import VadIU
from retico.agent.utils import Color as C

import numpy as np
import webrtcvad


class VADDebug(AbstractConsumingModule):
    @staticmethod
    def name():
        return "VAD Debug Module"

    @staticmethod
    def description():
        return "VAD Debug"

    @staticmethod
    def input_ius():
        return [VadIU]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_is_speaking = True

    def process_iu(self, input_iu):
        if input_iu.is_speaking != self.last_is_speaking:
            self.last_is_speaking = input_iu.is_speaking
            print(C.yellow + "VAD DEBUG")
            print("\tis_speaking: ", input_iu.is_speaking)
            print(C.end)


class VADModule(AbstractModule):
    @staticmethod
    def name():
        return "VAD Module"

    @staticmethod
    def description():
        return "VAD"

    @staticmethod
    def input_ius():
        return [AudioIU]

    @staticmethod
    def output_iu():
        return VadIU

    def __init__(self, chunk_time, sample_rate, mode=3, **kwargs):
        super().__init__(**kwargs)
        self.vad = webrtcvad.Vad(mode=mode)
        self.sample_rate = sample_rate
        self.chunk_time = chunk_time

        assert chunk_time in [
            0.01,
            0.02,
            0.03,
        ], f"webrtc.Vad must use frames of 10, 20 or 30 ms but got {int(chunk_time*1000)}"

    def process_iu(self, input_iu):
        output_iu = self.create_iu()
        output_iu.is_speaking = self.vad.is_speech(input_iu.raw_audio, self.sample_rate)
        return output_iu


def test_vad():
    from retico.core.audio.io import MicrophoneModule

    sample_rate = 16000
    chunk_time = 0.01
    chunk_size = int(chunk_time * sample_rate)
    bytes_per_sample = 2

    in_mic = MicrophoneModule(
        chunk_size=chunk_size,
        rate=sample_rate,
        sample_width=bytes_per_sample,
    )
    vad = VADModule(chunk_time=chunk_time, sample_rate=sample_rate, mode=3)
    vad_debug = VADDebug()

    # Connect
    in_mic.subscribe(vad)
    vad.subscribe(vad_debug)

    in_mic.run()
    vad.run()
    vad_debug.run()

    input()

    in_mic.stop()
    vad.stop()
    vad_debug.stop()


if __name__ == "__main__":
    test_vad()
