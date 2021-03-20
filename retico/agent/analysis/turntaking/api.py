from argparse import ArgumentParser
from os.path import join
from os import makedirs, walk
import time
import flask


from retico.agent.analysis.analysis import get_interaction_data
from retico.agent.analysis.turntaking.api_utils import jsonify_data

from retico.agent.analysis.analysis import Analysis


global aggregate_data
global ROOT
# global dialog
# global hparams
# global wav_file
# global interaction
# global all_turns

aggregate_data = None
ROOT = ""


TMP = "/tmp/audio"
makedirs(TMP, exist_ok=True)


app = flask.Flask(__name__)


@app.route("/api/interactions", methods=["GET"])
def interactions():
    ret = {"interactions": []}
    for root, _, files in walk(ROOT):
        if "dialog.wav" in files:
            ret["interactions"].append(root.replace(ROOT + "/", ""))
    return ret


@app.route("/api/audio/<path:interaction>", methods=["GET"])
def audio(interaction):
    wav_path = join(ROOT, interaction, "dialog.wav")
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


@app.route("/api/turn_audio/<idx>", methods=["GET"])
def turn_audio(idx=None):
    if idx is not None:
        return flask.send_file(join(TMP, f"turn_{idx}.wav"))
    else:
        return "error"


#########################################################
# Single
#########################################################


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
    elif data == "anno":
        ret = Analysis.annotation(interaction_dir)
    elif data == "turn_opportunity":
        ret = Analysis.agent_possible_onset_events(interaction_dir)
    elif data == "trp_info":
        ret = Analysis.trp_info(interaction_dir)
    return ret


#########################################################
# AGGREGATE
#########################################################
@app.route("/api/aggregate/<name>", methods=["GET"])
def aggregate(name):
    if name == "stats":
        global aggregate_data
        if aggregate_data is None:
            aggregate_data = Analysis.aggregate(ROOT)
        return aggregate_data
    else:
        return "error"


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
