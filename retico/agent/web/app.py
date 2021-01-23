import argparse
import asyncio
import logging
import json
import os
import uuid
import pyaudio

from aiohttp import web
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription

import queue
from retico.core.abstract import AbstractProducingModule
from retico.core.audio.io import StreamingSpeakerModule
from retico.core.audio.common import AudioIU


logger = logging.getLogger("pc")
pcs = set()

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 96000
# CHUNK = 960
CHUNK = 960 * 2
# CHUNK = 960 * 4

ROOT = os.path.dirname(__file__)


class AudioTrack(MediaStreamTrack):
    """
    A audio stream track that transforms frames from an another track.
    """

    kind = "audio"

    def __init__(self, track, audio_buffer):
        super().__init__()
        self.track = track
        self.audio_buffer = audio_buffer

    async def recv(self):
        frame = await self.track.recv()
        # print(frame.sample_rate)  # 48000
        # print(frame.samples)  # 960
        # print(frame.format)  # s16
        # print(frame.layout)  # stereo
        self.audio_buffer.put(frame.to_ndarray().tobytes())
        return frame


class WebAioRTCMicrophoneModule(AbstractProducingModule):
    """A module that produces IUs containing audio signals that are captures by
    a microphone."""

    @staticmethod
    def name():
        return "Microphone Module"

    @staticmethod
    def description():
        return "A prodicing module that records audio from microphone."

    @staticmethod
    def output_iu():
        return AudioIU

    def __init__(self, chunk_size, rate=48000, sample_width=2, **kwargs):
        """
        Initialize the Microphone Module.

        Args:
            chunk_size (int): The number of frames that should be stored in one
                AudioIU
            rate (int): The frame rate of the recording
            sample_width (int): The width of a single sample of audio in bytes.
        """
        super().__init__(**kwargs)
        self.chunk_size = chunk_size
        self.rate = rate
        self.sample_width = sample_width
        self.audio_buffer = queue.Queue()

    def process_iu(self, input_iu):
        if not self.audio_buffer:
            return None
        sample = self.audio_buffer.get()
        output_iu = self.create_iu()
        output_iu.set_audio(sample, self.chunk_size, self.rate, self.sample_width)
        return output_iu


mic = WebAioRTCMicrophoneModule(chunk_size=CHUNK, rate=RATE)
m2 = StreamingSpeakerModule(CHUNK, rate=RATE)


async def index(request):
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


async def javascript(request):
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pc_id = "PeerConnection(%s)" % uuid.uuid4()
    pcs.add(pc)

    def log_info(msg, *args):
        logger.info(pc_id + " " + msg, *args)

    log_info("Created for %s", request.remote)

    @pc.on("track")
    def on_track(track):
        log_info("Track %s received", track.kind)

        if track.kind == "audio":
            local_audio = AudioTrack(track, mic.audio_buffer)
            pc.addTrack(local_audio)

    # handle offer
    await pc.setRemoteDescription(offer)

    # send answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )


async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="WebRTC audio / video / data-channels demo"
    )
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP server (default: 8080)"
    )
    parser.add_argument("--verbose", "-v", action="count")
    parser.add_argument("--write-audio", help="Write received audio to a file")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/offer", offer)
    mic.subscribe(m2)

    mic.run()
    m2.run()
    web.run_app(app, access_log=None, host=args.host, port=args.port, ssl_context=None)

    input()
    mic.stop()
    m2.stop()
