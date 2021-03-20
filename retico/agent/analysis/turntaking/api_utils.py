from os.path import join

import torch
import torchaudio
import torchaudio.transforms as AT
import torchaudio.functional as AF


def time_to_samples(t, sr):
    return int(t * sr)


def get_turn(
    turns,
    turn_index,
    pre_pad,
    post_pad=0.75,
    waveform=None,
    sr=None,
    use_features=False,
    tmp_dir="/tmp/audio",
):
    turn = turns[turn_index]

    if turn["end_time"] - turn["start_time"] < 0.4:
        return None, None

    if turn["end_time"] < 0:
        return None, None

    if turn["name"] == "user":
        pre_pad = 0.75

    channel = 1 if turn["name"] == "user" else 0
    if waveform is not None:
        wf = waveform[
            channel,
            time_to_samples(turn["start_time"], sr)
            - time_to_samples(pre_pad, sr) : time_to_samples(turn["end_time"], sr)
            + time_to_samples(post_pad, sr),
        ]
        x = wf.unsqueeze(0)

        wavpath = join(tmp_dir, f"turn_{turn_index}.wav")
        torchaudio.save(wavpath, src=x, sample_rate=sr)
        # print("save: ", wavpath)

    features = {}
    if use_features:
        features = extract_features(x, sr)
        features["statistics"] = {
            "n_words": len(turn["utterance"].split()),
            "duration": round(turn["end_time"] - turn["start_time"], 2),
            "sample_rate": sr,
        }

    if "eot" in turn:
        features["eot"] = turn["eot"]
        features["tokens"] = turn["tokens"]
    return turn, features


def jsonify_data(interaction):
    for name, tfo in interaction["tfo"].items():
        interaction["tfo"][name] = {
            "starts": tfo[:, 0].tolist(),
            "ends": tfo[:, 1].tolist(),
            "duration": tfo[:, 2].tolist(),
        }
    return interaction


def extract_features(x, sr):
    step = 0.01
    fft_time = 0.05
    n_mels = 128
    n_mfcc = 40
    n_fft = int(fft_time * sr)
    hop_length = int(step * sr)
    spec = AT.MelSpectrogram(
        sample_rate=sr, n_fft=n_fft, hop_length=hop_length, n_mels=n_mels, f_max=8000
    )(x)[0]
    intensity = spec.mean(dim=0).log()
    spec = AT.AmplitudeToDB()(spec)
    mfcc = AT.MFCC(
        sample_rate=sr,
        n_mfcc=n_mfcc,
        melkwargs={
            "n_fft": n_fft,
            "hop_length": hop_length,
            "n_mels": n_mels,
            "f_max": 8000,
        },
    )(x)[0]
    mfcc = (mfcc - mfcc.mean(dim=1, keepdim=True)) / mfcc.std(dim=1, keepdim=True)
    pitch_feature = AF.compute_kaldi_pitch(
        x,
        sample_rate=sr,
        frame_length=fft_time * 1000,
        frame_shift=step * 1000,
        snip_edges=True,
        min_f0=70,
        max_f0=350,
        penalty_factor=0.01,
    )
    pitch = pitch_feature[0]
    return {
        "Waveform": x[0],
        "MelSpectrogram": spec,
        "MFCC": mfcc,
        "Pitch": pitch,
        "Intensity": intensity,
    }
