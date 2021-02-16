from boto3 import Session
from contextlib import closing
from datetime import datetime
from os import makedirs, listdir
from os.path import join
import json
import subprocess
import wave

from retico.core.text.common import GeneratedTextIU
from retico.core.audio.common import SpeechIU
from retico.core import abstract

"""
Amazon Polly

Uses credentials at $HOME/.aws/credentials

SSML
----

DOCS:   https://docs.aws.amazon.com/polly/latest/dg/supportedtags.html

Neural TTS:

Coversational style:    Yes
Speakers:               ['Matthew', 'Joanna']
Prosody:                [Volume, rate]
"""


class TTSPolly(object):
    SAMPLE_RATES = [8000, 16000, 22000, 24000]

    def __init__(
        self,
        sample_rate=16000,
        gender="female",
        language_code="en-US",
        speaking_rate=None,
        engine="neural",
        audio_output_format="pcm",
        output_word_times=False,
    ):
        assert (
            sample_rate in self.SAMPLE_RATES
        ), f"Non-valid sample_rate {sample_rate}. Please choose {self.SAMPLE_RATES}"
        self.sample_rate = str(sample_rate)
        self.audio_output_format = audio_output_format
        self.gender = gender
        self.speaking_rate = speaking_rate
        self.language_code = language_code
        self.engine = engine
        self.output_word_times = output_word_times

        self.session = Session()
        self.client = self.session.client("polly")

        self.voices = self._get_voices()
        self.voice = self.voices[self.gender][0]

    def _get_voices(self):
        valid_voices = {"female": [], "male": []}
        voice_dict = self.client.describe_voices()
        for voice in voice_dict["Voices"]:
            lang = voice["LanguageCode"]
            if voice["Id"] not in ["Matthew", "Joanna"]:
                continue

            if lang == self.language_code:
                if voice["Gender"].lower() == "female":
                    valid_voices["female"].append(voice)
                else:
                    valid_voices["male"].append(voice)
        assert (
            len(valid_voices["male"]) > 0 or len(valid_voices["female"]) > 0
        ), "No voices"
        return valid_voices

    def text_to_ssml(self, text, rate=None):
        s = "<speak>"
        s += '<amazon:domain name="conversational">'

        if rate is not None:
            s += f'<prosody rate="{rate}%">'

        # Finally add the pitch and text
        s += text

        # Close prosody tag
        if rate is not None:
            s += f"</prosody>"

        # close conversational/speak tags
        s += "</amazon:domain>"
        s += "</speak>"
        return s

    def response_marks_reader(self, response_marks):
        with closing(response_marks["AudioStream"]) as stream:
            data_strings = stream.read().decode().replace("'", "").split("\n")[:-1]
        words = []
        starts = []
        ends = []
        for row in data_strings:
            row = json.loads(row)
            words.append(row["value"])
            starts.append(int(row["time"]) / 1000)  # / 1000)
            # starts.append(int(row["start"]))  # / 1000)
            # ends.append(int(row["end"]))  # / 1000)
        return words, starts, ends

    def tts(self, text):
        text = self.text_to_ssml(text, self.speaking_rate)

        # Request speech synthesis
        response_audio = self.client.synthesize_speech(
            Engine=self.engine,
            LanguageCode=self.voice["LanguageCode"],
            Text=text,
            TextType="ssml",
            OutputFormat=self.audio_output_format,
            SampleRate=self.sample_rate,
            VoiceId=self.voice["Id"],
        )

        with closing(response_audio["AudioStream"]) as stream:
            raw_audio = stream.read()

        # add timing info of words
        if self.output_word_times:
            response_marks = self.client.synthesize_speech(
                Engine=self.engine,
                LanguageCode=self.voice["LanguageCode"],
                Text=text,
                TextType="ssml",
                OutputFormat="json",
                VoiceId=self.voice["Id"],
                SpeechMarkTypes=["word"],
            )
            words, starts, ends = self.response_marks_reader(response_marks)
            duration = len(raw_audio) / 2.0 / float(self.sample_rate)
            return words, starts, ends, duration, raw_audio
        else:
            return None, None, None, None, raw_audio


class AmazonTTSModule(abstract.AbstractModule):
    """A Google TTS Module that uses Googles TTS service to synthesize audio."""

    CACHE_DIR = "/tmp"

    @staticmethod
    def name():
        return "Amazon Polly TTS Module"

    @staticmethod
    def description():
        return "A module that uses Amazon Polly TTS to synthesize audio."

    @staticmethod
    def input_ius():
        return [GeneratedTextIU]

    @staticmethod
    def output_iu():
        return SpeechIU

    def __init__(
        self,
        sample_rate=16000,
        bytes_per_sample=2,
        output_word_times=False,
        tts_sample_rate=16000,
        cache_dir="/tmp",
        record=False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.sample_rate = sample_rate
        self.polly_sample_rate = tts_sample_rate
        self.tts = TTSPolly(
            sample_rate=tts_sample_rate, output_word_times=output_word_times
        )
        self.bytes_per_sample = bytes_per_sample
        self.record = record

        # tmp files
        self.cache_dir = cache_dir
        if self.cache_dir is None:
            self.cache_dir = self.CACHE_DIR
        self.cache_dir = join(self.cache_dir, "tts")
        makedirs(self.cache_dir, exist_ok=True)  # cache path

    def save_audio_file(self, raw_audio, text=None):
        if text is None:
            text = "tts"
        elif isinstance(text, list):
            text = "_".join(text[:3])

        time = datetime.now().strftime("%H_%M_%S")
        raw_wav_path = join(self.cache_dir, time + "_" + text + ".wav")

        with wave.open(raw_wav_path, "w") as obj:
            obj.setnchannels(1)
            obj.setsampwidth(2)
            obj.setframerate(self.polly_sample_rate)
            obj.writeframesraw(raw_audio)
        return raw_wav_path

    def resample_sox(self, wav_path):
        new_path = wav_path.replace(".wav", f"_sr-{self.sample_rate}.wav")
        subprocess.call(["sox", wav_path, "-r", str(self.sample_rate), new_path])
        return new_path

    def read_audio(self, wav_path):
        with wave.open(wav_path, "rb") as wav_file:
            w_length = wav_file.getnframes()
            raw_audio = wav_file.readframes(w_length)
        return raw_audio, w_length

    def resample_bytes(self, raw_audio, text=None):
        # 1. save raw_audio to a file PATH.wav
        # 2. sox resample file -> PATH2.wav
        # 3. read PATH2.wav
        wav_path = self.save_audio_file(raw_audio, text)
        new_wav_path = self.resample_sox(wav_path)
        raw_audio, _ = self.read_audio(new_wav_path)
        return raw_audio

    def stop(self, **kwargs):
        super().stop(**kwargs)

    def process_iu(self, input_iu):
        output_iu = self.create_iu(input_iu)
        if input_iu.get_text() != "":
            words, starts, ends, duration, raw_audio = self.tts.tts(input_iu.get_text())

            if self.sample_rate != self.polly_sample_rate:
                raw_audio = self.resample_bytes(raw_audio, words)
            elif self.record:
                _ = self.save_audio_file(raw_audio, words)

            nframes = len(raw_audio) / self.bytes_per_sample
            output_iu.set_audio(
                raw_audio, nframes, self.sample_rate, self.bytes_per_sample
            )
            output_iu.words = words
            output_iu.starts = starts
            output_iu.ends = ends
            output_iu.duration = duration
        output_iu.dispatch = input_iu.dispatch
        return output_iu


if __name__ == "__main__":

    tts = TTSPolly()
    raw_audio = tts.tts("hello there and back again")
