from boto3 import Session
from contextlib import closing
import json

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
    def __init__(
        self,
        sample_rate=16000,
        gender="female",
        language_code="en-US",
        speaking_rate=None,
        engine="neural",
        audio_output_format="pcm",
    ):
        self.sample_rate = str(sample_rate)
        self.audio_output_format = audio_output_format
        self.gender = gender
        self.speaking_rate = speaking_rate
        self.language_code = language_code
        self.engine = engine

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
            starts.append(int(row["start"]) / 1000)
            ends.append(int(row["end"]) / 1000)
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
        # response_marks = self.client.synthesize_speech(
        #     Engine=self.engine,
        #     LanguageCode=voice["LanguageCode"],
        #     Text=text,
        #     TextType="ssml",
        #     OutputFormat="json",
        #     VoiceId=voice["Id"],
        #     SpeechMarkTypes=["word"],
        # )
        # words, starts, ends = self.response_marks_reader(response_marks)
        # return words, starts, ends, response_audio["AudioStream"]
        return raw_audio


class AmazonTTSModule(abstract.AbstractModule):
    """A Google TTS Module that uses Googles TTS service to synthesize audio."""

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

    def __init__(self, sample_rate=16000, bytes_per_sample=2, caching=True, **kwargs):
        super().__init__(**kwargs)
        self.caching = caching
        self.tts = TTSPolly(sample_rate=sample_rate)
        self.bytes_per_sample = bytes_per_sample
        self.sample_rate = self.tts.sample_rate

    def process_iu(self, input_iu):
        output_iu = self.create_iu(input_iu)
        raw_audio = self.tts.tts(input_iu.get_text())
        nframes = len(raw_audio) / self.bytes_per_sample
        output_iu.set_audio(raw_audio, nframes, self.sample_rate, self.bytes_per_sample)
        output_iu.dispatch = input_iu.dispatch
        return output_iu


if __name__ == "__main__":

    tts = TTSPolly()
    raw_audio = tts.tts("hello there and back again")
