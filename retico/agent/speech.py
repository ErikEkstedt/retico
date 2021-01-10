from retico.core.abstract import AbstractModule, AbstractConsumingModule
from retico.core.audio.common import DispatchedAudioIU, SpeechIU
from retico.core.audio.io import (
    AudioDispatcherModule,
    StreamingSpeakerModule,
)
from retico.modules.amazon.tts import AmazonTTSModule
from retico.modules.google.tts_new import GoogleTTSModule


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


class TTSDebug(AbstractConsumingModule):
    @staticmethod
    def name():
        return "TTSDebug Module"

    @staticmethod
    def description():
        return "Print out values"

    @staticmethod
    def input_ius():
        return [SpeechIU]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def process_iu(self, input_iu):
        print("\twords: ", input_iu.words)
        print("\tstarts: ", input_iu.starts)
        print("\tends: ", input_iu.ends)
        print("AudioIU:")
        print("\traw_audio: ", len(input_iu.raw_audio))
        print("\trate: ", input_iu.rate)
        print("\tnframes: ", input_iu.nframes)
        print("\tsample_width: ", input_iu.sample_width)


class AudioDispatcherDebug(AbstractConsumingModule):
    @staticmethod
    def name():
        return "AudioDispatcherDebug Module"

    @staticmethod
    def description():
        return "Print out values"

    @staticmethod
    def input_ius():
        return [DispatchedAudioIU]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def process_iu(self, input_iu):
        print("completion: ", input_iu.completion)  # % of utterance done
        print("is_dispatching: ", input_iu.is_dispatching)
        print("AudioIU:")
        print("\traw_audio: ", len(input_iu.raw_audio))
        print("\trate: ", input_iu.rate)
        print("\tnframes: ", input_iu.nframes)
        print("\tsample_width: ", input_iu.sample_width)


# TODO
# Extend AudioDispatcherModule with not only providing `completion` (percentage completed of total utterance) but also
# include `words_left`, `seconds_left`.
# This data is given if using amazon tts with `output_word_times=True`.
# This makes it easier to infer if we should 'allow' interruptions or not. Only using a percentage might fail on
# long utterances.


class Speech(object):
    """
    Connect the tts component of the Speech-class to a module which outputs `GeneratedTextIU`
    """

    def __init__(
        self,
        chunk_time,
        sample_rate,
        bytes_per_sample,
        tts_client="google",
        output_word_times=False,
        debug=False,
    ):
        self.chunk_time = chunk_time
        self.sample_rate = sample_rate
        self.chunk_size = int(chunk_time * sample_rate)
        self.bytes_per_sample = bytes_per_sample
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
                caching=False,
                output_word_times=output_word_times,
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
            continuous=False,
            silence=None,
            interrupt=True,
        )
        self.streaming_speaker = StreamingSpeakerModule(
            self.chunk_size, rate=sample_rate, sample_width=bytes_per_sample
        )

        if debug:
            self.tts_debug = TTSDebug()
            self.audio_dispatcher_debug = AudioDispatcherDebug()

    def connect_components(self):
        self.tts.subscribe(self.audio_dispatcher)
        self.audio_dispatcher.subscribe(self.streaming_speaker)
        if self.debug:
            self.tts.subscribe(self.tts_debug)
            # self.audio_dispatcher.subscribe(self.audio_dispatcher_debug)

    def setup(self):
        self.tts.setup()
        self.audio_dispatcher.setup()
        self.streaming_speaker.setup()

    def run_components(self, run_setup=True):
        self.tts.run(run_setup=run_setup)
        self.audio_dispatcher.run(run_setup=run_setup)
        self.streaming_speaker.run(run_setup=run_setup)
        if self.debug:
            # self.audio_dispatcher_debug.run(run_setup=run_setup)
            self.tts_debug.run(run_setup=run_setup)

    def stop_components(self):
        self.tts.stop()
        self.audio_dispatcher.stop()
        self.streaming_speaker.stop()
        if self.debug:
            # self.audio_dispatcher_debug.stop()
            self.tts_debug.stop()


def test_speech():
    from retico.core.text.asr import TextDispatcherModule

    sample_rate = 16000
    chunk_time = 0.5
    bytes_per_sample = 2

    sample_text = "Hello there, I am a nice bot here to help you with anything that you might need. I can be interrupted and I will always be nice about it."

    speech = Speech(
        chunk_time,
        sample_rate,
        bytes_per_sample,
        tts_client="amazon",
        output_word_times=True,
        debug=True,
    )

    text = TextDispatcherModule()

    speech.connect_components()
    text.subscribe(speech.tts)

    speech.run_components()
    text.run()

    input_iu = text.create_iu(None)
    input_iu.payload = sample_text
    input_iu.dispatch = True
    text.append(input_iu)

    input()

    speech.stop_components()
    text.stop()


if __name__ == "__main__":
    test_speech()
