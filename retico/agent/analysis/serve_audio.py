from os.path import exists
import flask

app = flask.Flask(__name__)


@app.route("/api/audio/<path:audio>")
def audio(audio):
    print("Audio: ", audio)
    if audio.endswith(".wav"):
        audio = "/" + audio
        if exists(audio):
            print("serve: ", audio)
            return flask.send_file(audio)
        else:
            print("Dont Exist: ", audio)
            return "error"
    else:
        return "error"


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("--port", type=int, default=5002)
    parser.add_argument("--no_debug", action="store_true")
    args = parser.parse_args()

    debug = not args.no_debug
    app.run(debug=debug, port=args.port)
