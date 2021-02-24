import logging
import time
import queue
import pyaudio
from os import makedirs
from os.path import join

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

CHANNELS = 1

# logging.basicConfig(filename="Hearing.log", level=logging.INFO)

# Temporary hack
environ[
    "GOOGLE_APPLICATION_CREDENTIALS"
] = "/home/erik/projects/data/GOOGLE_SPEECH_CREDENTIALS.json"


class MicrophoneOutputBypass(AbstractProducingModule):
    """A module that produces IUs containing audio signals that are captures by
    a microphone."""

    # DEVICE = "pulse_sink_2"
    DEVICE = "zoom_sink"

    @staticmethod
    def name():
        return "Microphone Module"

    @staticmethod
    def description():
        return "A prodicing module that records audio from microphone."

    @staticmethod
    def output_iu():
        return AudioIU

    def callback(self, in_data, frame_count, time_info, status):
        """The callback function that gets called by pyaudio.

        Args:
            in_data (bytes[]): The raw audio that is coming in from the
                microphone
            frame_count (int): The number of frames that are stored in in_data
        """
        self.audio_buffer.put(in_data)
        return (in_data, pyaudio.paContinue)

    def get_device_index(self):
        bypass_index = None
        for i in range(self._p.get_device_count()):
            info = self._p.get_device_info_by_index(i)
            if info["name"] == self.DEVICE:
                bypass_index = i
                break
        return bypass_index

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

        self._p = pyaudio.PyAudio()

        self.device_index = self.get_device_index()
        assert (
            self.device_index is not None
        ), "Did not find bypass device -> Check JACK/Carla/Catia settings"

        self.audio_buffer = queue.Queue()
        self.stream = None

    def process_iu(self, input_iu):
        if not self.audio_buffer:
            return None
        sample = self.audio_buffer.get()
        output_iu = self.create_iu()
        output_iu.set_audio(sample, self.chunk_size, self.rate, self.sample_width)
        return output_iu

    def setup(self):
        """Set up the microphone for recordzing."""
        p = self._p
        self.stream = p.open(
            format=p.get_format_from_width(self.sample_width),
            channels=CHANNELS,
            rate=self.rate,
            input=True,
            output=False,
            stream_callback=self.callback,
            frames_per_buffer=self.chunk_size,
            input_device_index=self.device_index,
            start=False,
        )
        print("BYPASS SETUP")
        print("format", p.get_format_from_width(self.sample_width))
        print("channels", CHANNELS)
        print("rate", self.rate)
        print("frames_per_buffer", self.chunk_size)
        print("input_device_index", self.device_index)

    def prepare_run(self):
        if self.stream:
            self.stream.start_stream()

    def shutdown(self):
        """Close the audio stream."""
        self.stream.stop_stream()
        self.stream.close()
        self.stream = None
        self.audio_buffer = queue.Queue()


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

    CACHE_DIR = "/tmp"

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
        bypass=False,
        cache_dir="/tmp",
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

        self.cache_dir = cache_dir

        if self.use_iasr:
            self.use_asr = True

        # Components that are always used
        if bypass:
            self.in_mic = MicrophoneOutputBypass(
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
            self.cache_dir = join(cache_dir, "hearing")
            makedirs(self.cache_dir, exist_ok=True)
            print("Hearing: ", self.cache_dir)
            wav_filename = join(self.cache_dir, "user_audio.wav")
            self.audio_record = AudioRecorderModule(
                wav_filename, rate=sample_rate, sample_width=bytes_per_sample
            )
            self.in_mic.subscribe(self.audio_record)

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

    def setup(self, **kwargs):
        self.in_mic.setup(**kwargs)
        if self.use_asr:
            self.asr.setup(**kwargs)
        if self.use_iasr:
            self.iasr.setup(**kwargs)
        if self.record:
            self.audio_record.setup(**kwargs)
        logging.info(f"{self.name}: Setup")

    def run(self, **kwargs):
        self.in_mic.run(**kwargs)
        self.vad_frames.run(**kwargs)

        if self.use_asr:
            self.asr.run(**kwargs)

        if self.use_iasr:
            self.iasr.run(**kwargs)

        if self.record:
            self.audio_record.run(**kwargs)

        if self.debug:
            if self.use_asr:
                self.asr_debug.run(**kwargs)
                # self.iasr_debug.run(run_setup=run_setup)
        logging.info(f"{self.name}: run @ {time.time()}")

    def stop(self, **kwargs):
        self.in_mic.stop(**kwargs)
        self.vad_frames.stop(**kwargs)

        if self.use_asr:
            self.asr.stop(**kwargs)

        if self.use_iasr:
            self.iasr.stop(**kwargs)

        if self.record:
            self.audio_record.stop(**kwargs)

        if self.debug:
            if self.use_asr:
                self.asr_debug.stop(**kwargs)
        logging.info(f"{self.name}: stop_components @ {time.time()}")


def test_hearing(args):
    import sys

    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        use_asr=args.use_asr,
        cache_dir="/home/erik/.cache/agent/hearing",
        record=args.record,
        debug=True,
        bypass=args.bypass,
    )

    print(hearing)
    print(hearing.cache_dir)
    hearing.run()

    try:
        input()
    except KeyboardInterrupt:
        pass
    print("stop")
    hearing.stop()
    print("stop")

    sys.exit(0)


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("--chunk_time", type=float, default=0.01)
    parser.add_argument("--sample_rate", type=int, default=16000)
    parser.add_argument("--bytes_per_sample", type=int, default=2)
    parser.add_argument("--use_asr", action="store_true")
    parser.add_argument("--bypass", action="store_true")
    parser.add_argument("--record", action="store_true")

    args = parser.parse_args()
    test_hearing(args)
