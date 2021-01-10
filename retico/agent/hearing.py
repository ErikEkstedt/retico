import logging
import time

from retico.core.abstract import AbstractConsumingModule
from retico.core.audio.io import MicrophoneModule
from retico.core.debug.general import CallbackModule
from retico.core.text.asr import IncrementalizeASRModule
from retico.core.text.common import SpeechRecognitionIU
from retico.modules.google.asr import GoogleASRModule

from retico.agent.utils import Color as C

from os import environ

"""
The Hearing component of the Spoken Dialog System.

Takes a `GeneratedTextIU` and, using tts from google/amazon or similar, produces output audio.

Metrics
-------

* We want to how long the silences are
    - Use a VAD to incrementally tell the silence duration
    - Use sensible interval i.e. 0.05, 0.1, 0.15, 0.2, etc (seconds)

These metrics may then be used by EOTModules & BCModules to tell whether the incomming speech is complete or if some
reaction is plausable.

Thoughts
--------
* The IncrementalizeASRModule is pretty slow (using python list iteration to check if the new word is part of the given words)
    - When debuggin we see many more prints from the ASR module than that of the IASR module. It lags significantly
      behind...
    - When do we need the IASR module?
"""


logging.basicConfig(filename="Hearing.log", level=logging.INFO)

# Temporary hack
environ[
    "GOOGLE_APPLICATION_CREDENTIALS"
] = "/home/erik/projects/data/GOOGLE_SPEECH_CREDENTIALS.json"


class ASRDebugModule(AbstractConsumingModule):
    @staticmethod
    def name():
        return "ASR Debug Module"

    @staticmethod
    def description():
        return "Print out values"

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU]

    def __init__(self, incremental=False, **kwargs):
        super().__init__(**kwargs)
        self.incremental = incremental

    def process_iu(self, input_iu):
        if self.incremental:
            color = C.pink
            if input_iu.committed:
                color = C.yellow
            print(
                f"{color}IASR: {input_iu.text}\nstability: {input_iu.stability}\ncommitted: {input_iu.committed}{C.end}"
            )
        else:
            color = C.blue
            if input_iu.final:
                color = C.green
            print(
                f"{color}ASR: {input_iu.text}\nstability: {input_iu.stability}\nfinal: {input_iu.final}{C.end}"
            )


class Hearing(object):
    """
    The Hearing component of the Spoken Dialog System.

    Components:
        - MicrophoneModule
        - ASRModule
        - IncrementalizeASRModule
    """

    def __init__(
        self,
        chunk_time,
        sample_rate,
        bytes_per_sample,
        language="en-US",
        nchunks=20,
        debug=False,
    ):
        self.sample_rate = sample_rate
        self.chunk_time = chunk_time
        self.chunk_size = int(chunk_time * sample_rate)
        self.bytes_per_sample = bytes_per_sample
        self.debug = debug

        # Components
        self.in_mic = MicrophoneModule(
            chunk_size=self.chunk_size,
            rate=self.sample_rate,
            sample_width=self.bytes_per_sample,
        )
        self.asr = GoogleASRModule(
            language=language,
            nchunks=nchunks,  # m chunks to trigger a new prediction
            rate=self.sample_rate,
        )
        self.iasr = IncrementalizeASRModule(
            threshold=0.8
        )  # Gets only the newly added words at each increment

        if self.debug:
            # self.iasr_debug = ASRDebugModule(incremental=True)
            self.asr_debug = ASRDebugModule()

        logging.info(f"{self.name}: Initialized @ {time.time()}")

    @property
    def name(self):
        return self.__class__.__name__

    def __repr__(self):
        s = "\n" + "=" * 40
        s += "\n" + self.__class__.__name__
        s += f"\nsample_rate: {self.sample_rate}"
        s += f"\nchunk_time: {self.chunk_time}"
        s += f"\nchunk_size: {self.chunk_size}"
        s += f"\nbytes_per_sample: {self.bytes_per_sample}"
        s += f"\ndebug: {self.debug}"
        s += "\n" + "=" * 40
        return s

    def connect_components(self):
        self.in_mic.subscribe(self.asr)
        self.asr.subscribe(self.iasr)
        if self.debug:
            # self.iasr.subscribe(self.iasr_debug)
            self.asr.subscribe(self.asr_debug)
        logging.info(f"{self.name}: Connected Components")

    def setup(self):
        self.in_mic.setup()
        self.asr.setup()
        self.iasr.setup()
        logging.info(f"{self.name}: Setup")

    def run_components(self, run_setup=True):
        self.in_mic.run(run_setup=run_setup)
        self.asr.run(run_setup=run_setup)
        self.iasr.run(run_setup=run_setup)
        if self.debug:
            # self.iasr_debug.run(run_setup=run_setup)
            self.asr_debug.run(run_setup=run_setup)
        logging.info(
            f"{self.name}: run_components (run_setup={run_setup}) @ {time.time()}"
        )

    def stop_components(self):
        self.in_mic.stop()
        self.asr.stop()
        self.iasr.stop()
        if self.debug:
            # self.iasr_debug.stop()
            self.asr_debug.stop()
        logging.info(f"{self.name}: stop_components @ {time.time()}")


def test_hearing():
    sample_rate = 16000
    chunk_time = 0.01
    bytes_per_sample = 2

    hearing = Hearing(
        chunk_time=chunk_time,
        sample_rate=sample_rate,
        bytes_per_sample=bytes_per_sample,
        debug=True,
    )
    print(hearing)
    hearing.connect_components()
    hearing.run_components()
    try:
        input()
    except KeyboardInterrupt:
        pass
    hearing.stop_components()


def test_vad():
    pass


if __name__ == "__main__":

    test_hearing()
