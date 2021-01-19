from retico.core.debug.general import CallbackModule
from retico.core.audio.io import (
    AudioDispatcherModule,
    StreamingSpeakerModule,
)
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
        tts_client="google",
        output_word_times=False,
        debug=False,
        **kwargs,
    ):
        super().__init__(**kwargs)
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
        self.tts.setup()
        self.audio_dispatcher.setup()
        self.streaming_speaker.setup()

    def run(self, **kwargs):
        self.tts.run(**kwargs)
        self.audio_dispatcher.run(**kwargs)
        self.streaming_speaker.run(**kwargs)
        if self.debug:
            self.audio_dispatcher_debug.run(**kwargs)
            self.tts_debug.run(**kwargs)

    def stop(self, **kwargs):
        self.tts.stop(**kwargs)
        self.audio_dispatcher.stop(**kwargs)
        self.streaming_speaker.stop(**kwargs)
        if self.debug:
            self.audio_dispatcher_debug.stop(**kwargs)
            self.tts_debug.stop(**kwargs)


def test_speech():
    from retico.core.text.asr import TextDispatcherModule
    import time

    sample_rate = 16000
    chunk_time = 0.1
    bytes_per_sample = 2

    speech = Speech(
        chunk_time,
        sample_rate,
        bytes_per_sample,
        tts_client="amazon",
        output_word_times=True,
        debug=False,
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

    time.sleep(4)
    input_iu = text.create_iu(None)
    input_iu.payload = ""
    input_iu.dispatch = False
    text.append(input_iu)
    input()

    speech.stop()
    text.stop()


if __name__ == "__main__":
    test_speech()
