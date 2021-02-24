from argparse import ArgumentParser
from os.path import join
import flask

global dialog
global hparams
global wav_file


app = flask.Flask(__name__)


@app.route("/api/file/<name>", methods=["GET"])
def serve_file(name):
    if name == "hparams":
        return flask.send_file(hparams)
    elif name == "dialog":
        return flask.send_file(dialog)
    else:
        return "Error"


@app.route("/api/audio", methods=["GET"])
def audio():
    return flask.send_file(wav_file)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--root",
        type=str,
        default="/tmp/agent/baseline",
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    dialog = join(args.root, "dialog.json")
    hparams = join(args.root, "hparams.json")
    wav_file = join(args.root, "dialog.wav")
    print(wav_file)
    app.run(debug=args.debug, port=args.port)
