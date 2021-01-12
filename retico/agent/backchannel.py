import requests
import json
import time

import wave

from retico.core.abstract import AbstractConsumingModule
from retico.core.audio.io import AudioIU
from retico.core.audio.io import SpeakerModule
from retico.core.text.common import SpeechRecognitionIU

from retico.agent.vad import VadIU

URL_TRP = "http://localhost:5000/trp"

# TODO:
# Add a backchannel ranker
# choose suitable backchannel from a list of alternatives
# mhm, right, yes, no, go on, tell me more, etc


class BackChannelModule(AbstractConsumingModule):
    """
    A BackChannelModule that uses the microphone audio stream to infer VAD and ASR output to infer wheather a
    backchannel should be used. This is independent from other Speech modules to provide fast feedback.

    The module checks if there has been silence from the user over `self.`
    """

    @staticmethod
    def name():
        return "BackChannelModule"

    @staticmethod
    def description():
        return "A modules which omit fast backchannels"

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU, VadIU]

    def __init__(
        self,
        cooldown=2.0,
        bc_trp_thresh_min=0.1,
        bc_trp_thresh_max=0.4,
        vad_time_min=0.1,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.cooldown = cooldown

        # trp
        self.bc_trp_thresh_min = bc_trp_thresh_min
        self.bc_trp_thresh_max = bc_trp_thresh_max
        self.trp_clear = False

        # Vad times
        self.vad_time_min = vad_time_min
        self.vad_time_clear = False
        self.bc_last_time = 0

        # playback
        audio = wave.open("/home/erik/projects/data/backchannels/mm.wav", "rb")
        self.backchannel_audio = audio.readframes(audio.getnframes())
        self.speaker = SpeakerModule(
            rate=16000, sample_width=2
        )  # hardcoded for sample audio

        self.speaker.run()  # run the speaker component

    def get_eot(self, text):
        json_data = {"text": text}
        response = requests.post(URL_TRP, json=json_data)
        d = json.loads(response.content.decode())
        return d["trp"][-1]  # only care about last token

    def handle_asr(self, input_iu):
        if not input_iu.final:
            trp = self.get_eot(input_iu.text)
            if self.bc_trp_thresh_min <= trp <= self.bc_trp_thresh_max:
                self.trp_clear = True
            else:
                self.trp_clear = False
        else:
            self.trp_clear = False

        self.speak()

    def handle_vad(self, input_iu):
        if input_iu.is_speaking == False:
            if input_iu.silence_time > self.vad_time_min:
                self.vad_time_clear = True
                # print("BC-VAD-time: ", True)
        else:
            self.vad_time_clear = False
        self.speak()

    def speak(self):
        if self.vad_time_clear and self.trp_clear:
            if time.time() - self.bc_last_time > self.cooldown:
                print("===========")
                print("BACKCHANNEL")
                print("===========")
                output_iu = AudioIU
                output_iu.raw_audio = self.backchannel_audio
                self.speaker.process_iu(output_iu)
                self.bc_last_time = time.time()

    def process_iu(self, input_iu):
        if isinstance(input_iu, SpeechRecognitionIU):
            self.handle_asr(input_iu)
        elif isinstance(input_iu, VadIU):
            self.handle_vad(input_iu)

    def shutdown(self):
        self.speaker.stop()


def test_bc():
    from retico.agent.hearing import Hearing

    chunk_time = 0.01
    sample_rate = 16000
    chunk = int(chunk_time * sample_rate)
    hearing = Hearing(
        chunk_time=chunk_time, sample_rate=sample_rate, bytes_per_sample=2
    )
    bc = BackChannelModule()

    hearing.vad.subscribe(bc)
    hearing.asr.subscribe(bc)

    hearing.run_components()
    bc.run()

    input()

    hearing.stop_components()
    bc.stop()


if __name__ == "__main__":
    test_bc()
