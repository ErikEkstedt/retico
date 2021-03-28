from argparse import ArgumentParser
from os.path import join, exists
from os import makedirs, walk
import time
import flask


from retico.agent.utils import read_json
from retico.agent.analysis.analysis import Analysis, get_interaction_data
from retico.agent.analysis.utils import read_audio
from retico.agent.analysis.turntaking.api_utils import jsonify_data

import torchaudio


global ROOT
global dialog_audio
global aggregate_data
global last_aggregate_root

ROOT = ""
dialog_audio = None
last_aggregate_root = ""
aggregate_data = None


TMP = "/tmp/audio"
CACHE = "/home/erik/.cache/agent/turn_audio"
makedirs(TMP, exist_ok=True)


app = flask.Flask(__name__)

###############################################################
# Files on system
###############################################################


@app.route("/api/roots", methods=["GET"])
def root():
    return {"roots": [ROOT]}


@app.route("/api/interactions", methods=["GET"])
def interactions():
    ret = {"interactions": []}
    for root, _, files in walk(ROOT):
        if "dialog.wav" in files:
            ret["interactions"].append(root.replace(ROOT + "/", ""))
    return ret


###############################################################
# Interaction Data
###############################################################
@app.route("/api/audio/<path:interaction>", methods=["GET"])
def audio(interaction):
    wav_path = join(ROOT, interaction, "dialog.wav")
    print("wav_path: ", wav_path)
    return flask.send_file(wav_path)


@app.route("/api/dialog/<path:interaction>", methods=["GET"])
def dialog_data(interaction):
    interaction_dir = join(ROOT, interaction)
    data = get_interaction_data(interaction_dir)
    data = jsonify_data(data)
    return data


@app.route("/api/turns/<path:interaction>", methods=["GET"])
def turns(interaction):
    interaction_dir = join(ROOT, interaction)
    turns = Analysis.get_turns(interaction_dir)
    return turns


@app.route(
    "/api/turn_audio/<idx>/<start_time>/<end_time>/<path:interaction>", methods=["GET"]
)
def turn_audio(idx=None, start_time=None, end_time=None, interaction=None):
    global dialog_audio

    if (
        idx is not None
        and start_time is not None
        and end_time is not None
        and interaction is not None
    ):

        dirpath = join(CACHE, interaction)
        makedirs(dirpath, exist_ok=True)
        audiopath = join(dirpath, f"turn_{idx}.wav")

        if not exists(audiopath):
            start_time = float(start_time)
            end_time = float(end_time)
            if dialog_audio is None:
                wav_path = join(ROOT, interaction, "dialog.wav")
                dialog_audio = read_audio(wav_path)
                print("Interaction: ", interaction)
                print("idx: ", idx)
                print("start: ", start_time)
                print("end: ", end_time)
                print("waveform: ", dialog_audio["waveform"].shape)

            sr = dialog_audio["sample_rate"]
            s = int(start_time * sr)
            s -= int(0.5 * sr)
            if s < 0:
                s = 0
            e = int(end_time * sr)
            e += int(0.5 * sr)
            print("START: ", s, type(s))
            print("END: ", e, type(e))
            x = dialog_audio["waveform"][:, s:e]
            torchaudio.save(audiopath, src=x, sample_rate=sr)
        print("PATH: ", audiopath)
        return flask.send_file(audiopath)
    return "error"


@app.route("/api/interaction/<data>/<path:interaction>", methods=["GET"])
def interaction_data(data=None, interaction=None):
    if data is None or interaction is None:
        return "error"

    interaction_dir = join(ROOT, interaction)
    ret = "error"
    if data == "tfo":
        ret = Analysis.tfo(interaction_dir)
        ret["agent"] = ret["agent"].t().tolist()
        ret["user"] = ret["user"].t().tolist()
    elif data == "fallback":
        ret = Analysis.fallbacks(interaction_dir)
    elif data == "omitted_turns":
        ret = Analysis.get_omitted_turns(interaction_dir)
    elif data == "anno":
        ret = Analysis.annotation(interaction_dir)
    elif data == "turn_opportunity":
        ret = Analysis.agent_possible_onset_events(interaction_dir)
    elif data == "trp_info":
        ret = Analysis.trp_info(interaction_dir)
    elif data == "hparams":
        ret = read_json(join(interaction_dir, "hparams.json"))
    elif data == "responsiveness_and_interruption":
        ret = Analysis.responsiveness_and_interruption(interaction_dir)
    return ret


#########################################################
# AGGREGATE
#########################################################
@app.route("/api/aggregate/<path:root>", methods=["GET"])
def aggregate(root):
    global last_aggregate_root
    global aggregate_data
    print("root: ", root)

    if root == last_aggregate_root and aggregate_data is not None:
        return aggregate_data
    else:
        last_aggregate_root = root
        aggregate_data = Analysis.aggregate(ROOT)
        return aggregate_data


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--root",
        type=str,
        default="/tmp/agent/baseline",
    )
    parser.add_argument("--no_debug", action="store_true")
    parser.add_argument("--port", type=int, default=5005)
    args = parser.parse_args()

    ROOT = args.root
    print("ROOT: ", ROOT)

    # dialog = join(args.root, "dialog.json")
    # hparams = join(args.root, "hparams.json")
    # wav_file = join(args.root, "dialog.wav")
    # interaction = get_interaction_data(
    #     args.root, include_dialog=True, include_audio=True
    # )
    # interaction = jsonify_data(interaction)

    # # turns = data["dialog"]["turns"]
    # # Audio
    # sr = interaction["audio"]["sample_rate"]
    # waveform = interaction["audio"]["waveform"]
    # waveform[1] = waveform[1] - waveform[1].min()
    # waveform[1] /= waveform[1].max()
    # print(waveform.shape)

    # # waveform[1] -= waveform[1].mean()
    # pre_pad = 0
    # post_pad = 0.5
    # all_turns = []
    # t = time.time()
    # for turn_index in range(len(interaction["dialog"]["turns"])):
    #     turn, features = get_turn(
    #         interaction["dialog"]["turns"],
    #         turn_index,
    #         pre_pad,
    #         post_pad,
    #         waveform,
    #         sr,
    #         tmp_dir=TMP,
    #     )
    #     if turn is not None:
    #         # all_turns.append({"turn": turn, "features": features})
    #         all_turns.append({"turn": turn})
    # print("Features extraction: ", round(time.time() - t, 2))

    # interaction.pop("audio")

    debug = not args.no_debug
    app.run(debug=debug, port=args.port)
