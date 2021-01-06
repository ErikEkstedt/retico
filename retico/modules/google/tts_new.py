from retico.core import abstract
from retico.core.text.common import GeneratedTextIU
from retico.core.audio.common import SpeechIU

from google.cloud import texttospeech_v1beta1 as texttospeech
from os import environ


# Temporary hack
environ[
    "GOOGLE_APPLICATION_CREDENTIALS"
] = "/home/erik/projects/data/GOOGLE_SPEECH_CREDENTIALS.json"


class TTSGoogle(object):
    def __init__(
        self,
        gender="female",
        speaking_rate=1.0,
        pitch=0,
        sample_rate=16000,
        language_code="en-US",
        name="en-US-Wavenet-C",
    ):
        self.gender = gender
        self.speaking_rate = speaking_rate
        self.pitch = pitch
        self.sample_rate = sample_rate
        self.language_code = language_code
        self.name = name

        # tts
        self.client = texttospeech.TextToSpeechClient()
        self.voices = self._list_voices()
        self.voice_parameters = self._voice_parameters()
        self.audio_config = self._audio_config()

    def __repr__(self):
        s = "Google TTS Client"
        s += f"\ngender: {self.gender}"
        s += f"\nspeaking_rate: {self.speaking_rate}"
        s += f"\npitch: {self.pitch}"
        s += f"\nsample_rate: {self.sample_rate}"
        s += f"\nlanguage_code: {self.language_code}"
        s += f"\nname: {self.name}"
        return s

    def _list_voices(self):
        """ Performs the list voices request """
        voices = {"female": [], "male": []}
        for v in self.client.list_voices(language_code="en").voices:
            if any([t for t in ["GB", "AU", "US"] if t in v.name]):
                if "wavenet" in v.name.lower():
                    if "female" in v.ssml_gender.name.lower():
                        voices["female"].append(v)
                    else:
                        voices["male"].append(v)
        return voices

    def _voice_parameters(self):
        ssml_gender1 = self.get_ssml_gender(self.gender)
        return texttospeech.VoiceSelectionParams(
            language_code=self.language_code, name=self.name, ssml_gender=ssml_gender1
        )

    def _audio_config(self):
        return texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            speaking_rate=self.speaking_rate,
            pitch=self.pitch,
            sample_rate_hertz=self.sample_rate,
        )

    def get_ssml_gender(self, gender):
        if gender.lower() == "female":
            ssml_gender = texttospeech.SsmlVoiceGender.FEMALE
        else:
            ssml_gender = texttospeech.SsmlVoiceGender.MALE
        return ssml_gender

    def text_to_ssml_marks(self, text):
        ssml = "<speak>"
        for word in text.split():
            ssml += f'<mark name="{word}"/>{word} '
        ssml += "</speak>"
        return ssml

    def tts(self, text):
        ssml = self.text_to_ssml_marks(text)
        synthesis_input = texttospeech.SynthesisInput(ssml=ssml)
        request = texttospeech.types.SynthesizeSpeechRequest(
            input=synthesis_input,
            voice=self.voice_parameters,
            audio_config=self.audio_config,
            enable_time_pointing=["SSML_MARK"],
        )
        response = self.client.synthesize_speech(request=request)

        starts = []
        words = []
        for t in response.timepoints:
            starts.append(t.time_seconds)
            words.append(t.mark_name)
        return words, starts, response.audio_content


class GoogleTTSModule(abstract.AbstractModule):
    """A Google TTS Module that uses Googles TTS service to synthesize audio."""

    @staticmethod
    def name():
        return "Google TTS Module"

    @staticmethod
    def description():
        return "A module that uses Google TTS to synthesize audio."

    @staticmethod
    def input_ius():
        return [GeneratedTextIU]

    @staticmethod
    def output_iu():
        return SpeechIU

    def __init__(self, sample_rate=16000, bytes_per_sample=2, caching=True, **kwargs):
        super().__init__(**kwargs)
        self.caching = caching
        self.gtts = TTSGoogle(sample_rate=sample_rate)
        self.bytes_per_sample = bytes_per_sample
        self.sample_rate = self.gtts.sample_rate

    def process_iu(self, input_iu):
        output_iu = self.create_iu(input_iu)
        _, _, raw_audio = self.gtts.tts(input_iu.get_text())
        nframes = len(raw_audio) / self.bytes_per_sample
        output_iu.set_audio(raw_audio, nframes, self.sample_rate, self.bytes_per_sample)
        # output_iu.words = words
        # output_iu.starts = starts
        output_iu.dispatch = input_iu.dispatch
        return output_iu


if __name__ == "__main__":

    # tts = TTSGoogle()
    # words, starts, response = tts.tts("hello there you handsome fool!")

    tts = GoogleTTSModule()
