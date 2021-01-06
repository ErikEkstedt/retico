"""
Some sample code to play with in order to understand:
    'TurnTakingDialogueManagerModule' in retico/modules/simulation/dm.py
"""

from retico.core import abstract
from retico.core.text.common import SpeechRecognitionIU, GeneratedTextIU
from retico.core.audio.io import (
    MicrophoneModule,
    AudioDispatcherModule,
    StreamingSpeakerModule,
)
from retico.modules.google.asr import GoogleASRModule
from retico.core.text.asr import IncrementalizeASRModule, TextDispatcherModule
from retico.core.debug.general import CallbackModule
from retico.modules.google.tts_new import GoogleTTSModule
from retico.modules.amazon.tts import AmazonTTSModule

from os import environ

# Temporary hack
environ[
    "GOOGLE_APPLICATION_CREDENTIALS"
] = "/home/erik/projects/data/GOOGLE_SPEECH_CREDENTIALS.json"


class ModuleBase(object):
    def _run(self):
        raise NotImplementedError()

    def _stop(self):
        raise NotImplementedError()

    def run(self):
        print(f"Running: {self.__class__.__name__}")
        self._run()
        input()
        self._stop()
        print(f"Stopped: {self.__class__.__name__}")


class CustomModule(abstract.AbstractConsumingModule):
    """A debug module that prints the IUs that are coming in."""

    @staticmethod
    def name():
        return "Custom Module"

    @staticmethod
    def description():
        return "A consuming module that displays IU infos in the console."

    @staticmethod
    def input_ius():
        return [abstract.IncrementalUnit]

    def process_iu(self, input_iu):
        print("Debug")
        print("text: ", input_iu.text)
        print("stability: ", input_iu.stability)
        if hasattr(input_iu, "committed"):
            print("committed: ", input_iu.committed)
        if hasattr(input_iu, "finality"):
            print("finality: ", input_iu.finality)


class WordTrigger(abstract.AbstractModule):
    """A debug module that prints the IUs that are coming in."""

    @staticmethod
    def name():
        return "Word Trigger Module"

    @staticmethod
    def description():
        return "Triggers on a specific word"

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU]

    @staticmethod
    def output_iu():
        return GeneratedTextIU

    def __init__(self, word_trigger="elephant", **kwargs):
        super().__init__(**kwargs)
        self.word_trigger = word_trigger

    def process_iu(self, input_iu):
        if self.word_trigger in input_iu.text:
            output_iu = self.create_iu()
            output_iu.text = f"I am triggered. Heard the word: {self.word_trigger}"
            return output_iu
        else:
            return None


class Hearing(object):
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
            self.console_out = CallbackModule(
                callback=lambda x: print(f"IASR: {x.text}\n{x.stability}")
            )

    def connect_components(self):
        self.in_mic.subscribe(self.asr)
        self.asr.subscribe(self.iasr)
        if self.debug:
            self.iasr.subscribe(self.console_out)

    def setup(self):
        self.in_mic.setup()
        self.asr.setup()
        self.iasr.setup()

    def run_components(self, run_setup=True):
        self.in_mic.run(run_setup=run_setup)
        self.asr.run(run_setup=run_setup)
        self.iasr.run(run_setup=run_setup)
        if self.debug:
            self.console_out.run(run_setup=run_setup)

    def stop_components(self):
        self.in_mic.stop()
        self.asr.stop()
        self.iasr.stop()
        if self.debug:
            self.console_out.stop()


class Speech(object):
    def __init__(
        self,
        chunk_time,
        sample_rate,
        bytes_per_sample,
        tts_client="google",
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
        self.streaming_speaker = StreamingSpeakerModule(
            self.chunk_size, rate=sample_rate, sample_width=bytes_per_sample
        )

    def connect_components(self):
        self.tts.subscribe(self.audio_dispatcher)
        self.audio_dispatcher.subscribe(self.streaming_speaker)

    def setup(self):
        self.tts.setup()
        self.audio_dispatcher.setup()
        self.streaming_speaker.setup()

    def run_components(self, run_setup=True):
        self.tts.run(run_setup=run_setup)
        self.audio_dispatcher.run(run_setup=run_setup)
        self.streaming_speaker.run(run_setup=run_setup)

    def stop_components(self):
        self.tts.stop()
        self.audio_dispatcher.stop()
        self.streaming_speaker.stop()


class RepeatAgent(ModuleBase):
    def __init__(
        self,
        sample_rate=16000,
        chunk_time=0.01,
        bytes_per_sample=2,
        tts_client="google",
        debug=False,
    ):
        self.chunk_time = chunk_time
        self.sample_rate = sample_rate
        self.chunk_size = int(chunk_time * sample_rate)
        self.bytes_per_sample = bytes_per_sample
        self.tts_client = tts_client
        self.debug = debug

        # Hearing =======================================================
        self.hearing = Hearing(chunk_time, sample_rate, bytes_per_sample, debug=debug)

        # Brain/DM/TurnTaking =========================================
        self.text_dispatcher = TextDispatcherModule()
        # self.asr_print = CustomModule()

        # Speech/Output ===============================================
        self.speech = Speech(
            chunk_time,
            sample_rate,
            bytes_per_sample,
            tts_client=tts_client,
            debug=debug,
        )

        self._connect_components()

    def _connect_components(self):
        """
        Connects all the components (subscribe)
        """
        # Hearing
        self.hearing.connect_components()

        # DM/Brain
        self.hearing.asr.subscribe(
            self.text_dispatcher
        )  # connect whats been heard to text dispatcher
        self.text_dispatcher.subscribe(
            self.speech.tts
        )  # connect text dispatcher with speech

        # Speech
        self.speech.connect_components()  # connect speech

    def _run(self):
        self.hearing.run_components()
        self.text_dispatcher.run()
        self.speech.run_components()

    def _stop(self):
        self.hearing.stop_components()
        self.text_dispatcher.stop()
        self.speech.stop_components()


class SDSAgent(ModuleBase):
    def __init__(
        self, sample_rate=16000, chunk_time=0.01, bytes_per_sample=2, debug=False
    ):
        self.chunk_time = chunk_time
        self.sample_rate = sample_rate
        self.chunk_size = int(chunk_time * sample_rate)
        self.bytes_per_sample = bytes_per_sample
        self.debug = debug

        # Hearing =======================================================
        self.hearing = Hearing(chunk_time, sample_rate, bytes_per_sample, debug=False)

        # Brain/DM/TurnTaking =========================================
        self.text_dispatcher = TextDispatcherModule()
        # self.asr_print = CustomModule()

        # Speech/Output ===============================================
        self.speech = Speech(chunk_time, sample_rate, bytes_per_sample, debug=debug)

        self._connect_components()

    def _connect_components(self):
        """
        Connects all the components (subscribe)
        """
        # Hearing
        self.hearing.connect_components()

        # DM/Brain
        self.hearing.asr.subscribe(
            self.text_dispatcher
        )  # connect whats been heard to text dispatcher
        self.text_dispatcher.subscribe(
            self.speech.tts
        )  # connect text dispatcher with speech

        # Speech
        self.speech.connect_components()  # connect speech

    def _run(self):
        self.hearing.run_components()
        self.text_dispatcher.run()
        self.speech.run_components()

    def _stop(self):
        self.hearing.stop_components()
        self.text_dispatcher.stop()
        self.speech.stop_components()


if __name__ == "__main__":

    sample_rate = 16000
    chunk_time = 0.05
    bytes_per_sample = 2
    print("sample_rate: ", sample_rate)
    print("chunk_time: ", chunk_time)
    print("bytes_per_sample: ", bytes_per_sample)

    # agent = RepeatAgent(
    #     sample_rate, chunk_time, bytes_per_sample, tts_client="google", debug=True
    # )
    # agent.run()

    agent = RepeatAgent(
        sample_rate, chunk_time, bytes_per_sample, tts_client="amazon", debug=True
    )
    agent.run()

    # repeat_demo()
