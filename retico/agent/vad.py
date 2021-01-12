from retico.core.abstract import (
    AbstractModule,
    IncrementalUnit,
    AbstractConsumingModule,
)
from retico.core.audio.common import AudioIU

from retico.agent.utils import Color as C

import webrtcvad


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
        self.last_silence_time = 0

    def process_iu(self, input_iu):
        if input_iu.silence_time != self.last_silence_time:
            self.last_silence_time = input_iu.silence_time
            print(C.yellow + "VAD")
            print("\tis_speaking: ", input_iu.is_speaking)
            print("\tsilence_time: ", input_iu.silence_time)
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
        self.chunk_time = chunk_time
        self.sample_rate = sample_rate
        self.silence_time = 0
        self.silence_discrete = 0

    def process_iu(self, input_iu):
        is_speaking = self.vad.is_speech(input_iu.raw_audio, self.sample_rate)
        output_iu = self.create_iu()
        if is_speaking:
            self.silence_time = 0
            self.silence_discrete = 0
            output_iu.set_is_speaking()
        else:
            self.silence_time += self.chunk_time
            self.silence_time = round(self.silence_time, 2)
            output_iu.set_silence_time(self.silence_time)
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
    vad_debug = VADDebug()
    vad = VADModule(
        chunk_time=chunk_time, sample_rate=sample_rate, silence_interval=0.05, mode=3
    )
    vad.subscribe(vad_debug)
    in_mic.subscribe(vad)

    in_mic.run()
    vad.run()
    vad_debug.run()

    input()

    in_mic.stop()
    vad.stop()
    vad_debug.stop()


if __name__ == "__main__":
    test_vad()
