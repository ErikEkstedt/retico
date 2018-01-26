"""
This module redefines the abstract classes to fit the needs of audio processing.
"""

from rtcmodules import abstract

class AudioIncrementalUnit(abstract.IncrementalUnit):
    """An audio incremental unit that receives raw audio data from a source.

    The audio contained should be monaural.

    Attributes:
        creator (AbstractModule): The module that created this IU
        previous_iu (IncrementalUnit): A link to the IU created before the
            current one.
        grounded_in (IncrementalUnit): A link to the IU this IU is based on.
        created_at (float): The UNIX timestamp of the moment the IU is created.
        raw_audio (bytes[]): The raw audio of this IU
        rate (int): The frame rate of this IU
        nframes (int): The number of frames of this IU
        sample_width (int): The bytes per sample of this IU
    """

    @staticmethod
    def type():
        return "Audio IU"

    def __init__(self, creator, iuid=0, previous_iu=None, grounded_in=None,
                 rate=None, nframes=None, sample_width=None, raw_audio=None):
        super().__init__(creator, iuid=iuid, previous_iu=previous_iu,
                         grounded_in=grounded_in, payload=raw_audio)
        self.raw_audio = raw_audio
        self.rate = rate
        self.nframes = nframes
        self.sample_width = sample_width

    def set_audio(self, raw_audio, nframes, rate, sample_width):
        """Sets the audio content of the IU."""
        self.raw_audio = raw_audio
        self.payload = raw_audio
        self.nframes = nframes
        self.rate = rate
        self.sample_width = self.sample_width

    def audio_length(self):
        """Return the length of the audio IU in seconds.

        Returns:
            float: Length of the audio in this IU in seconds.
        """
        return float(self.nframes) / float(self.rate)
