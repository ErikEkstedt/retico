from argparse import ArgumentParser
from os.path import join
import flask

from retico.agent.utils import read_json

global file
global wav_file

app = flask.Flask(__name__)


@app.route("/api/file", methods=["GET"])
def serve_file():
    return file


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

    file = read_json(join(args.root, "dialog.json"))
    wav_file = join(args.root, "dialog.wav")
    app.run(debug=args.debug, port=args.port)
