import pyaudio
import queue
from os.path import join
from os import makedirs

from retico.core.abstract import AbstractConsumingModule
from retico.core.audio.common import AudioIU
from retico.core.audio.io import (
    AudioDispatcherModule,
    StreamingSpeakerModule,
    AudioRecorderModule,
)
from retico.core.debug.general import CallbackModule
from retico.modules.amazon.tts import AmazonTTSModule
from retico.modules.google.tts_new import GoogleTTSModule

from retico.agent.utils import Color as C


"""
The Speech component of the Spoken Dialog System.

Takes a `GeneratedTextIU` and, using tts from google/amazon or similar, produces output audio.

Metrics
-------

* We want to know the text of what we are saying
* We want to know how many words/time left we have on our current utterance
    * Which words are completed?
    * Which words are left?

"""

# TODO
# Extend AudioDispatcherModule with not only providing `completion` (percentage completed of total utterance) but also
# include `words_left`, `seconds_left`.
# This data is given if using amazon tts with `output_word_times=True`.
# This makes it easier to infer if we should 'allow' interruptions or not. Only using a percentage might fail on
# long utterances.


class DeviceStreamSpeakerModule(AbstractConsumingModule):
    """A module that consumes Audio IUs and outputs them to the speaker of the
    machine. The audio output is streamed and thus the Audio IUs have to have
    exactly [chunk_size] samples."""

    TIMEOUT = 0.01
    CHANNELS = 1
    DEVICE = "zoom_source"
    # DEVICE = "pulse_source_2"

    @staticmethod
    def name():
        return "Streaming Speaker Module"

    @staticmethod
    def description():
        return "A consuming module that plays audio from speakers."

    @staticmethod
    def input_ius():
        return [AudioIU]

    @staticmethod
    def output_iu():
        return None

    def callback(self, in_data, frame_count, time_info, status):
        """The callback function that gets called by pyaudio."""
        if self.audio_buffer:
            try:
                audio_paket = self.audio_buffer.get(timeout=self.TIMEOUT)
                return (audio_paket, pyaudio.paContinue)
            except queue.Empty:
                pass
        return (b"\0" * frame_count * self.sample_width, pyaudio.paContinue)

    def __init__(
        self,
        chunk_size,
        rate=48000,
        sample_width=2,
        **kwargs,
    ):
        """Initialize the streaming speaker module.

        Args:
            chunk_size (int): The number of frames a buffer of the output stream
                should have.
            rate (int): The frame rate of the audio. Defaults to 44100.
            sample_width (int): The sample width of the audio. Defaults to 2.
        """
        super().__init__(**kwargs)
        self.chunk_size = chunk_size
        self.rate = rate
        self.sample_width = sample_width

        self._p = pyaudio.PyAudio()
        self.device_index = self.find_device_index()
        assert (
            self.device_index is not None
        ), "Could not find device index for {device_name}"
        self.audio_buffer = queue.Queue()
        self.stream = None

    def find_device_index(self):
        # find audio_sink_2 index
        device_index = None
        for i in range(self._p.get_device_count()):
            info = self._p.get_device_info_by_index(i)
            if info["name"] == self.DEVICE:
                device_index = i
                break
        return device_index

    def process_iu(self, input_iu):
        self.audio_buffer.put(input_iu.raw_audio)
        return None

    def setup(self):
        """Set up the speaker for speaking...?"""
        p = self._p
        self.stream = p.open(
            format=p.get_format_from_width(self.sample_width),
            channels=self.CHANNELS,
            rate=self.rate,
            input=False,
            output=True,
            output_device_index=self.device_index,
            stream_callback=self.callback,
            frames_per_buffer=self.chunk_size,
        )
        self.stream.start_stream()

    def shutdown(self):
        """Close the audio stream."""
        self.stream.stop_stream()
        self.stream.close()
        self.stream = None
        self.audio_buffer = queue.Queue()


class Speech:
    """
    Connect the tts component of the Speech-class to a module which outputs `GeneratedTextIU`
    """

    EVENT_SPEECH_STARTED = "event_speech_started"
    EVENT_SPEECH_ENDED = "event_speech_ended"

    @staticmethod
    def name():
        return "Speech Module"

    def __init__(
        self,
        chunk_time,
        sample_rate,
        bytes_per_sample,
        chunk_size=None,
        tts_client="google",
        output_word_times=False,
        record=False,
        debug=False,
        bypass=False,
        device_name="pulse_source_2",
        cache_dir="/tmp",
        result_dir="/tmp",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.chunk_time = chunk_time
        if chunk_size is None:
            self.chunk_size = chunk_size

        self.sample_rate = sample_rate
        self.chunk_size = int(chunk_time * sample_rate)
        self.bytes_per_sample = bytes_per_sample
        self.record = record
        self.debug = debug

        if tts_client.lower() == "google":
            self.tts = GoogleTTSModule(
                sample_rate=sample_rate,
                bytes_per_sample=bytes_per_sample,
                caching=False,
            )
        elif tts_client.lower() == "amazon":
            self.tts = AmazonTTSModule(
                sample_rate=sample_rate,
                bytes_per_sample=bytes_per_sample,
                output_word_times=output_word_times,
                polly_sample_rate=16000,
                cache_dir=cache_dir,
                record=record,
            )
        else:
            raise NotImplementedError(
                f'tts_client {tts_client} is not implemented. Try ["google", "amazon"]'
            )

        self.audio_dispatcher = AudioDispatcherModule(
            target_chunk_size=self.chunk_size,
            rate=sample_rate,
            sample_width=bytes_per_sample,
            speed=1.0,
            continuous=True,
            silence=None,
            interrupt=True,
        )

        if self.record:
            audio_dir = join(result_dir, "speech")
            makedirs(audio_dir, exist_ok=True)
            print("Speech: ", audio_dir)
            wav_filename = join(audio_dir, "agent_audio.wav")
            self.audio_recorder = AudioRecorderModule(
                wav_filename, rate=sample_rate, sample_width=bytes_per_sample
            )
            self.audio_dispatcher.subscribe(self.audio_recorder)

        if bypass:
            self.streaming_speaker = DeviceStreamSpeakerModule(
                self.chunk_size,
                rate=sample_rate,
                sample_width=bytes_per_sample,
                device_name=device_name,
            )
        else:
            self.streaming_speaker = StreamingSpeakerModule(
                self.chunk_size, rate=sample_rate, sample_width=bytes_per_sample
            )

        self.tts.subscribe(self.audio_dispatcher)
        self.audio_dispatcher.subscribe(self.streaming_speaker)

        if debug:
            self.tts_debug = CallbackModule(
                callback=lambda x: print(C.blue, f"TTS: {x.dispatch}", C.end)
            )
            self.tts.subscribe(self.tts_debug)
            self.audio_dispatcher_debug = CallbackModule(
                callback=lambda x: print(
                    C.green,
                    f"completion: {x.completion} is_dispatching: {x.is_dispatching}",
                    C.end,
                )
            )
            self.audio_dispatcher.subscribe(self.audio_dispatcher_debug)

    def setup(self, **kwargs):
        self.tts.setup(**kwargs)
        self.audio_dispatcher.setup(**kwargs)
        self.streaming_speaker.setup(**kwargs)

        if self.record:
            self.audio_recorder.setup(**kwargs)

    def run(self, **kwargs):
        self.tts.run(**kwargs)
        self.audio_dispatcher.run(**kwargs)
        self.streaming_speaker.run(**kwargs)
        if self.debug:
            self.audio_dispatcher_debug.run(**kwargs)
            self.tts_debug.run(**kwargs)
        if self.record:
            self.audio_recorder.run(**kwargs)

    def stop(self, **kwargs):
        self.tts.stop(**kwargs)
        self.audio_dispatcher.stop(**kwargs)
        self.streaming_speaker.stop(**kwargs)
        if self.debug:
            self.audio_dispatcher_debug.stop(**kwargs)
            self.tts_debug.stop(**kwargs)
        if self.record:
            self.audio_recorder.stop(**kwargs)


def test_speech(args):
    from retico.core.text.asr import TextDispatcherModule

    speech = Speech(
        chunk_time=args.speech_chunk_time,
        chunk_size=args.speech_chunk_size,
        sample_rate=args.speech_sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        tts_client="amazon",
        output_word_times=True,
        bypass=args.bypass,
        debug=True,
    )

    sample_text = "Hello there, I am a nice bot here to help you with anything that you might need. I can be interrupted and I will always be nice about it."
    text = TextDispatcherModule()

    # speech.connect_components()
    text.subscribe(speech.tts)
    speech.run()
    text.run()
    input_iu = text.create_iu(None)
    input_iu.payload = sample_text
    input_iu.dispatch = True
    text.append(input_iu)

    print("speaking...")
    # time.sleep(4)
    # input_iu = text.create_iu(None)
    # input_iu.payload = ""
    # input_iu.dispatch = False
    # text.append(input_iu)
    input()

    speech.stop()
    text.stop()


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("--speech_chunk_time", type=float, default=0.1)
    parser.add_argument("--speech_chunk_size", type=int, default=None)
    parser.add_argument("--speech_sample_rate", type=int, default=16000)
    parser.add_argument("--bytes_per_sample", type=int, default=2)
    parser.add_argument("--bypass", action="store_true")
    args = parser.parse_args()
    print("BYPASS: ", args.bypass)
    test_speech(args)
