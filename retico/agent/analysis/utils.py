from os.path import join, exists
import torchaudio

from retico.agent.utils import read_json


def read_audio(wav_path):
    y, sr = torchaudio.load(wav_path)
    return {"waveform": y, "sample_rate": sr}


def load_interaction(dialog_root):
    hparams = read_json(join(dialog_root, "hparams.json"))
    dialog = read_json(join(dialog_root, "dialog.json"))
    waveform = read_audio(join(dialog_root, "dialog.wav"))
    anno_path = join(dialog_root, "annotation.json")
    anno = None
    if exists(anno_path):
        anno = read_json(anno_path)
    return {"hparams": hparams, "dialog": dialog, "audio": waveform, "anno": anno}
