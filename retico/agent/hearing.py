import logging
import time
import queue

from retico.core.abstract import AbstractConsumingModule, AbstractProducingModule
from retico.core.audio.common import AudioIU
from retico.core.audio.io import MicrophoneModule, AudioRecorderModule
from retico.core.debug.general import CallbackModule
from retico.core.text.asr import IncrementalizeASRModule
from retico.core.text.common import SpeechRecognitionIU
from retico.core.text.io import TextRecorderModule
from retico.modules.google.asr import GoogleASRModule

from retico.agent.vad import VADFrames
from retico.agent.utils import Color as C

from os import environ

"""
The Hearing component of the Spoken Dialog System.

Takes a `GeneratedTextIU` and, using tts from google/amazon or similar, produces output audio.

Metrics
-------

* We want to how long the silences are
    - [x] Use a VAD to incrementally tell the silence duration
    - [ ] Use sensible interval i.e. 0.05, 0.1, 0.15, 0.2, etc (seconds)

These metrics may then be used by EOTModules & BCModules to tell whether the incomming speech is complete or if some
reaction is plausable.

Thoughts
--------
* The IncrementalizeASRModule is pretty slow (using python list iteration to check if the new word is part of the given words)
    - When debuggin we see many more prints from the ASR module than that of the IASR module. It lags significantly
      behind...
    - When do we need the IASR module?

hearing = Hearing()
hearing.in_mic # microphone
hearing.vad # vad-component
hearing.asr # asr-component
hearing.iasr # incremental-asr-component
"""


# logging.basicConfig(filename="Hearing.log", level=logging.INFO)

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


class AudioBufferWrapper(AbstractProducingModule):
    """A module that produces IUs containing audio signals that are captures by
    a microphone."""

    @staticmethod
    def name():
        return "Microphone Module"

    @staticmethod
    def description():
        return "A prodicing module that records audio from microphone."

    @staticmethod
    def output_iu():
        return AudioIU

    def __init__(self, chunk_size, rate=48000, sample_width=2, **kwargs):
        """
        Initialize the Microphone Module.

        Args:
            chunk_size (int): The number of frames that should be stored in one
                AudioIU
            rate (int): The frame rate of the recording
            sample_width (int): The width of a single sample of audio in bytes.
        """
        super().__init__(**kwargs)
        self.chunk_size = chunk_size
        self.rate = rate
        self.sample_width = sample_width
        self.audio_buffer = queue.Queue()

    def process_iu(self, input_iu):
        if not self.audio_buffer:
            return None
        sample = self.audio_buffer.get()
        output_iu = self.create_iu()
        output_iu.set_audio(sample, self.chunk_size, self.rate, self.sample_width)
        return output_iu


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
        chunk_time=None,
        chunk_size=None,
        sample_rate=16000,
        bytes_per_sample=2,
        language="en-US",
        nchunks=20,
        use_asr=True,
        use_iasr=False,
        record=False,
        debug=False,
        web_server=False,
    ):
        self.sample_rate = sample_rate
        assert (
            chunk_time is not None or chunk_size is not None
        ), "please provide either chunk_time or chunk_size"

        if chunk_size is not None:
            self.chunk_size = int(chunk_size)
            self.chunk_time = chunk_size / sample_rate
        else:
            self.chunk_time = chunk_time
            self.chunk_size = int(chunk_time * sample_rate)

        self.bytes_per_sample = bytes_per_sample
        self.use_asr = use_asr
        self.use_iasr = use_iasr
        self.record = record
        self.debug = debug

        if self.use_iasr:
            self.use_asr = True

        # Components that are always used
        if web_server:
            self.in_mic = AudioBufferWrapper(
                chunk_size=self.chunk_size,
                rate=self.sample_rate,
                sample_width=self.bytes_per_sample,
            )
        else:
            self.in_mic = MicrophoneModule(
                chunk_size=self.chunk_size,
                rate=self.sample_rate,
                sample_width=self.bytes_per_sample,
            )
        self.vad_frames = VADFrames(
            chunk_time=self.chunk_time,
            sample_rate=self.sample_rate,
            mode=3,
            debug=debug,
        )
        self.in_mic.subscribe(self.vad_frames)

        # Optional Components
        if self.use_asr:
            self.asr = GoogleASRModule(
                language=language,
                nchunks=nchunks,  # m chunks to trigger a new prediction
                rate=self.sample_rate,
            )
            self.in_mic.subscribe(self.asr)

        if self.use_iasr:
            self.iasr = IncrementalizeASRModule(
                threshold=0.8
            )  # Gets only the newly added words at each increment
            self.asr.subscribe(self.iasr)

        if self.record:
            wav_filename = "test.wav"
            self.audio_record = AudioRecorderModule(
                wav_filename, rate=sample_rate, sample_width=bytes_per_sample
            )
            self.in_mic.subscribe(self.audio_record)

            if self.use_asr:
                txt_filename = "test.txt"
                self.text_record = TextRecorderModule(txt_filename, separator="\t")
                self.asr.subscribe(self.text_record)
                txt_filename = "test_inc.txt"
                self.inc_text_record = TextRecorderModule(txt_filename, separator="\t")
                self.iasr.subscribe(self.inc_text_record)

        if self.debug:
            self.asr_debug = ASRDebugModule()
            if self.use_asr:
                self.asr.subscribe(self.asr_debug)

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
        s += f"\nrecord: {self.record}"
        s += f"\nuse_asr: {self.use_asr}"
        s += f"\ndebug: {self.debug}"
        s += "\n" + "=" * 40
        return s

    def setup(self):
        self.in_mic.setup()
        if self.use_asr:
            self.asr.setup()
            self.iasr.setup()
        if self.record:
            self.audio_record.setup()
            if self.use_asr:
                self.text_record.setup()
                self.inc_text_record.setup()
        logging.info(f"{self.name}: Setup")

    def run_components(self, run_setup=True):
        self.in_mic.run(run_setup=run_setup)
        self.vad_frames.run(run_setup=run_setup)

        if self.use_asr:
            self.asr.run(run_setup=run_setup)

        if self.use_iasr:
            self.iasr.run(run_setup=run_setup)

        if self.record:
            self.audio_record.run(run_setup=run_setup)

            if self.use_asr:
                self.text_record.run(run_setup=run_setup)

            if self.use_iasr:
                self.inc_text_record.run(run_setup=run_setup)

        if self.debug:
            if self.use_asr:
                self.asr_debug.run(run_setup=run_setup)
                # self.iasr_debug.run(run_setup=run_setup)
        logging.info(
            f"{self.name}: run_components (run_setup={run_setup}) @ {time.time()}"
        )

    def stop_components(self):
        self.in_mic.stop()
        self.vad_frames.stop()

        if self.use_asr:
            self.asr.stop()

        if self.use_iasr:
            self.iasr.stop()

        if self.record:
            self.audio_record.stop()
            if self.use_asr:
                self.text_record.stop()
            if self.use_iasr:
                self.inc_text_record.stop()
        if self.debug:
            if self.use_asr:
                self.asr_debug.stop()
        logging.info(f"{self.name}: stop_components @ {time.time()}")


def test_hearing(args):
    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        use_asr=args.use_asr,
        record=args.record,
        debug=args.debug,
    )

    print(hearing)
    hearing.run_components()
    try:
        input()
    except KeyboardInterrupt:
        pass
    hearing.stop_components()


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("--chunk_time", type=float, default=0.01)
    parser.add_argument("--sample_rate", type=int, default=16000)
    parser.add_argument("--bytes_per_sample", type=int, default=2)
    parser.add_argument("--use_asr", action="store_true")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    test_hearing(args)
