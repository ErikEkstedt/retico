from os.path import join, expanduser

from retico.core import abstract
from retico.core.audio.io import (
    MicrophoneModule,
    SpeakerModule,
    AudioDispatcherModule,
    StreamingSpeakerModule,
    AudioRecorderModule,
)
from retico.modules.google.asr import GoogleASRModule
from retico.core.debug.console import DebugModule
from retico.core.debug.general import CallbackModule
from retico.core.text.asr import TextDispatcherModule
from retico.modules.google.tts import GoogleTTSModule

import numpy as np
import torch
from research.turngpt.turngpt_chat import TurnGPTChat
from research.tokenizer import load_turngpt_tokenizer

MODELPATH = join(
    expanduser("~"),
    # "research/research/turngpt/runs/mock_checkpoints/ch_epoch=00-val_loss=2.3125.ckpt",
    "research/research/turngpt/runs/mock_checkpoints/ch_epoch=02-val_loss=2.3217.ckpt",
)


class CustomAudioModule(abstract.AbstractConsumingModule):
    """A debug module that prints the IUs that are coming in."""

    @staticmethod
    def name():
        return "Custom Module"

    @staticmethod
    def description():
        return "Playing aroung"

    @staticmethod
    def input_ius():
        return [abstract.IncrementalUnit]

    def __init__(self, chunk_size, rate=44100, memory=5, **kwargs):
        super().__init__(**kwargs)
        self.memory = memory
        self.chunk_size = chunk_size
        self.rate = rate

        memory_samples = int(rate * memory)
        self.data = np.zeros(memory_samples)

        self.count = 0

    def update_memory(self, new_val):
        l = new_val.shape[0]
        self.data[:-l] = self.data[l:]
        self.data[-l:] = new_val

    def process_iu(self, input_iu):
        b = np.frombuffer(bytes(input_iu.raw_audio), dtype=np.int16).astype(np.float32)
        self.update_memory(b)
        print("#" * int(np.abs(b).mean() / 80))


class CustomTextModule(abstract.AbstractConsumingModule):
    """A debug module that prints the IUs that are coming in."""

    @staticmethod
    def name():
        return "Custom Text Module"

    @staticmethod
    def description():
        return "Playing around"

    @staticmethod
    def input_ius():
        return [abstract.IncrementalUnit]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_utterance = ""
        self.last_final = 0
        self.model = TurnGPTChat.load_from_checkpoint(
            checkpoint_path=MODELPATH,
            tokenizer=load_turngpt_tokenizer(),
        )
        if torch.cuda.is_available():
            self.model = self.model.to("cuda")
        print("Model Loaded")

    def process_iu(self, input_iu):
        if input_iu.stability >= 0.8:
            # print("%s (%f) - %s" % (input_iu.text, input_iu.stability, input_iu.final))
            if input_iu.text != self.last_utterance:
                output = self.model.trp_from_strings(context=[input_iu.text])
                self.last_final = round(output["trp"][0, -1].item(), 2)
                self.last_utterance = input_iu.text
                s = f"{self.last_final} " + input_iu.text
                print(s)


def google_asr():
    m1 = MicrophoneModule(5000)
    m2 = GoogleASRModule("en-US")  # en-US or de-DE or ....
    m3 = CallbackModule(
        callback=lambda x: print("%s (%f) - %s" % (x.text, x.stability, x.final))
    )

    m1.subscribe(m2)
    m2.subscribe(m3)

    m1.run()
    m2.run()
    m3.run()

    input()

    m1.stop()
    m2.stop()
    m3.stop()


def audio():
    rate = 16000
    chunk_time = 0.1
    chunk_size = int(rate * chunk_time)
    sample_width = 2

    m1 = MicrophoneModule(chunk_size, rate=rate)
    m2 = StreamingSpeakerModule(chunk_size, rate)
    # db = DebugModule()
    db = CustomModule(chunk_size, rate=rate)

    m1.subscribe(m2)
    m1.subscribe(db)

    m1.run()
    m2.run()
    db.run()

    input()

    m1.stop()
    m2.stop()
    db.stop()


if __name__ == "__main__":

    # google_asr()

    m1 = MicrophoneModule(5000)
    m2 = GoogleASRModule("en-US")  # en-US or de-DE or ....
    m3 = CustomTextModule()

    m1.subscribe(m2)
    m2.subscribe(m3)

    m1.run()
    m2.run()
    m3.run()

    input()

    m1.stop()
    m2.stop()
    m3.stop()
