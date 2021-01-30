import time

from retico.core.abstract import AbstractModule, AbstractConsumingModule
from retico.core.debug.general import CallbackModule
from retico.core.audio.common import AudioIU

from retico.agent.common import VadIU
from retico.agent.utils import Color as C

import numpy as np
import webrtcvad


class VADFrames(AbstractModule):
    @staticmethod
    def name():
        return "VAD Module"

    @staticmethod
    def description():
        return "VAD"

    @staticmethod
    def input_ius():
        return [AudioIU]

    @staticmethod
    def output_iu():
        return VadIU

    def __init__(self, chunk_time, sample_rate, mode=3, debug=False, **kwargs):
        super().__init__(**kwargs)
        self.vad = webrtcvad.Vad(mode=mode)
        self.sample_rate = sample_rate
        self.chunk_time = chunk_time
        self.last_vad_state = None
        self.debug = debug

        if self.debug:
            self._debugger = CallbackModule(callback=self._debug)
            self.subscribe(self._debugger)

        assert chunk_time in [
            0.01,
            0.02,
            0.03,
        ], f"webrtc.Vad must use frames of 10, 20 or 30 ms but got {int(chunk_time*1000)}"

    def run(self, **kwargs):
        if self.debug:
            self._debugger.run()
        super().run(**kwargs)

    def stop(self, **kwargs):
        if self.debug:
            self._debugger.stop()
        super().stop(**kwargs)

    def _debug(self, input_iu):
        if input_iu.is_speaking != self.last_vad_state:
            self.last_vad_state = input_iu.is_speaking
            print(C.yellow + f"VAD DEBUG: is_speaking: {input_iu.is_speaking}" + C.end)

    def process_iu(self, input_iu):
        output_iu = self.create_iu()
        output_iu.is_speaking = self.vad.is_speech(input_iu.raw_audio, self.sample_rate)
        return output_iu


class VAD(AbstractModule):
    """
    The Voice Activity Detection module. This module takes VadIU units process by the VADFrames module which are
    aggregated over time in order to 'smooth' the signal. This component is useful for determining Turn onset and
    offset but also to recognize segments of silence inside of an utterance.


    E.g. A turn-base VAD module might use onset_time=.4 and offset_time=.75 which means that if a proportion of frames,
    larger than 'probability', during the onset_time duration is recognized the Vad state is true. Less active frames
    does not trigger the onset of the state. The offset interval is used in the same way but for silence. If sufficient
    amount of frames are silent (in the offset interval) the Vad state is de-activated.

    """

    EVENT_VAD_CHANGE = "event_vad_change"

    @staticmethod
    def name():
        return "VAD Module"

    @staticmethod
    def description():
        return "Speech Voice Activity based on vad_onset, vad_offset"

    @staticmethod
    def input_ius():
        return [VadIU]

    @staticmethod
    def output_iu():
        return VadIU

    def __init__(
        self,
        chunk_time,
        offset_time=0.5,
        onset_time=0.5,
        prob_thresh=0.9,
        debug=False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.started = False
        self.is_speaking = False
        self.probability = 0

        self.chunk_time = chunk_time
        self.prob_thresh = prob_thresh

        # Used to turn OFF speech activity
        self.offset_time = offset_time
        n_off = int(offset_time / chunk_time)  # number of frames to evaluate
        self.vad_off_context = np.zeros(n_off)

        # Used to turn ON speech activity
        self.onset_time = onset_time
        n_on = int(onset_time / chunk_time)
        self.vad_on_context = np.zeros(n_on)

        self.debug = debug
        if self.debug:
            self._debugger = CallbackModule(callback=self._debug)
            self.subscribe(self._debugger)

    def _debug(self, x):
        color = C.red
        if x.is_speaking:
            color = C.green
        print(
            color + f"SVAD: is_speaking: {x.is_speaking}, prob: {x.probability}" + C.end
        )

    def add_state(self, is_speaking):
        is_silent = (not is_speaking) * 1.0
        is_speaking *= 1.0

        self.vad_on_context = np.concatenate(
            (self.vad_on_context[1:], np.array((is_speaking,)))
        )
        self.vad_off_context = np.concatenate(
            (self.vad_off_context[1:], np.array((is_silent,)))
        )

    def output(self):
        output_iu = self.create_iu()
        output_iu.is_speaking = self.is_speaking
        output_iu.probability = self.probability
        return output_iu

    def run(self, **kwargs):
        if self.debug:
            self._debugger.run()
        return super().run(**kwargs)

    def stop(self, **kwargs):
        if self.debug:
            self._debugger.stop()
        return super().stop(**kwargs)

    def process_iu(self, input_iu):
        # if not self.started:
        #     self.started = True
        #     self.is_speaking = input_iu.is_speaking
        #     self.probability = self.vad_off_context.mean()
        #     self.event_call(
        #         self.EVENT_VAD_CHANGE,
        #         data={"is_speaking": self.is_speaking, "time": time.time()},
        #     )
        #     return self.output()

        self.add_state(input_iu.is_speaking)
        if self.is_speaking:
            if self.vad_off_context.mean() >= self.prob_thresh:
                self.is_speaking = False
                self.probability = self.vad_off_context.mean()
                self.event_call(
                    self.EVENT_VAD_CHANGE,
                    data={
                        "is_speaking": self.is_speaking,
                        "time": time.time() - self.offset_time,
                    },
                )
                return self.output()
        else:
            if self.vad_on_context.mean() >= self.prob_thresh:
                self.is_speaking = True
                self.probability = self.vad_on_context.mean()
                self.event_call(
                    self.EVENT_VAD_CHANGE,
                    data={
                        "is_speaking": self.is_speaking,
                        "time": time.time() - self.onset_time,
                    },
                )
                return self.output()


class VADModule(AbstractConsumingModule):
    """
    The Voice Activity Detection module. This module takes VadIU units process by the VADFrames module which are
    aggregated over time in order to 'smooth' the signal. This component is useful for determining Turn onset and
    offset but also to recognize segments of silence inside of an utterance.


    E.g. A turn-base VAD module might use onset_time=.4 and offset_time=.75 which means that if a proportion of frames,
    larger than 'probability', during the onset_time duration is recognized the Vad state is true. Less active frames
    does not trigger the onset of the state. The offset interval is used in the same way but for silence. If sufficient
    amount of frames are silent (in the offset interval) the Vad state is de-activated.

    """

    EVENT_VAD_TURN_CHANGE = "event_vad_turn_change"
    EVENT_VAD_IPU_CHANGE = "event_vad_ipu_change"
    EVENT_VAD_FAST_CHANGE = "event_vad_fast_change"

    @staticmethod
    def name():
        return "VAD Module"

    @staticmethod
    def description():
        return "Speech Voice Activity based on vad_onset, vad_offset"

    @staticmethod
    def input_ius():
        return [VadIU]

    def __init__(
        self,
        chunk_time,
        onset_time=0.2,
        turn_offset=0.75,
        ipu_offset=0.3,
        fast_offset=0.1,
        prob_thresh=0.9,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.chunk_time = chunk_time
        self.prob_thresh = prob_thresh

        self.turn_active = False
        self.turn_onset = onset_time
        self.turn_offset = turn_offset

        self.ipu_active = False
        self.ipu_onset = onset_time
        self.ipu_offset = ipu_offset

        self.fast_active = False
        self.fast_onset = onset_time
        self.fast_offset = fast_offset

        self.create_buffers()

    def create_buffers(self):
        # TURN ==================================
        n_off = int(self.turn_offset / self.chunk_time)  # number of frames to evaluate
        n_on = int(self.turn_onset / self.chunk_time)
        self.turn_off_buffer = np.zeros(n_off)
        self.turn_on_buffer = np.zeros(n_on)

        # IPU ==================================
        n_off = int(self.ipu_offset / self.chunk_time)  # number of frames to evaluate
        n_on = int(self.ipu_onset / self.chunk_time)
        self.ipu_off_buffer = np.zeros(n_off)
        self.ipu_on_buffer = np.zeros(n_on)

        # Fast ==================================
        n_off = int(self.fast_offset / self.chunk_time)  # number of frames to evaluate
        n_on = int(self.fast_onset / self.chunk_time)
        self.fast_off_buffer = np.zeros(n_off)
        self.fast_on_buffer = np.zeros(n_on)

    def debug_callback(self, module, event_name, data):
        color = C.red
        if data["active"]:
            color = C.green
        print(color + f"{event_name}: {data['active']}" + C.end)

    def add_state(self, is_speaking):
        is_silent = (not is_speaking) * 1.0
        is_speaking *= 1.0

        # TURN
        self.turn_on_buffer = np.concatenate(
            (self.turn_on_buffer[1:], np.array((is_speaking,)))
        )
        self.turn_off_buffer = np.concatenate(
            (self.turn_off_buffer[1:], np.array((is_silent,)))
        )

        # IPU
        self.ipu_on_buffer = np.concatenate(
            (self.ipu_on_buffer[1:], np.array((is_speaking,)))
        )
        self.ipu_off_buffer = np.concatenate(
            (self.ipu_off_buffer[1:], np.array((is_silent,)))
        )

        # Fast
        self.fast_on_buffer = np.concatenate(
            (self.fast_on_buffer[1:], np.array((is_speaking,)))
        )
        self.fast_off_buffer = np.concatenate(
            (self.fast_off_buffer[1:], np.array((is_silent,)))
        )

    def update(self, activity, on_buffer, off_buffer, offset_time, onset_time, event):
        if activity:
            if off_buffer.mean() >= self.prob_thresh:
                activity = False
                prob = off_buffer.mean()

                self.event_call(
                    event,
                    data={
                        "active": activity,
                        "time": time.time() - offset_time,
                    },
                )
        else:
            if on_buffer.mean() >= self.prob_thresh:
                activity = True
                prob = on_buffer.mean()
                self.event_call(
                    event,
                    data={
                        "active": activity,
                        "time": time.time() - onset_time,
                    },
                )
        return activity

    def process_iu(self, input_iu):
        """Adds incomming frame activity to buffers and omits event if relevant"""
        self.add_state(input_iu.is_speaking)

        self.turn_active = self.update(
            self.turn_active,
            self.turn_on_buffer,
            self.turn_off_buffer,
            self.turn_onset,
            self.turn_offset,
            self.EVENT_VAD_TURN_CHANGE,
        )

        self.ipu_active = self.update(
            self.ipu_active,
            self.ipu_on_buffer,
            self.ipu_off_buffer,
            self.ipu_onset,
            self.ipu_offset,
            self.EVENT_VAD_IPU_CHANGE,
        )

        self.fast_active = self.update(
            self.fast_active,
            self.fast_on_buffer,
            self.fast_off_buffer,
            self.fast_onset,
            self.fast_offset,
            self.EVENT_VAD_FAST_CHANGE,
        )


def test_vad_frames(args):
    from retico.core.audio.io import MicrophoneModule

    sample_rate = 16000
    chunk_size = int(args.chunk_time * sample_rate)
    bytes_per_sample = 2

    in_mic = MicrophoneModule(
        chunk_size=chunk_size,
        rate=sample_rate,
        sample_width=bytes_per_sample,
    )
    vad = VADFrames(
        chunk_time=args.chunk_time, sample_rate=sample_rate, mode=3, debug=True
    )

    # Connect
    in_mic.subscribe(vad)
    in_mic.run()
    vad.run()
    input()
    in_mic.stop()
    vad.stop()


def test_vad(args):
    from retico.agent.hearing import Hearing

    sample_rate = 16000
    bytes_per_sample = 2
    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=sample_rate,
        bytes_per_sample=bytes_per_sample,
        use_asr=False,
        record=False,
        debug=False,
    )
    vad = VAD(
        chunk_time=args.chunk_time,
        onset_time=args.onset,
        offset_time=args.offset,
        debug=True,
    )

    # Connect Components
    hearing.vad_frames.subscribe(vad)

    # run
    hearing.run_components()
    vad.run()
    print("VAD")
    try:
        input()
    except KeyboardInterrupt:
        pass
    hearing.stop_components()
    vad.stop()


def test_vad_module(args):
    from retico.agent.hearing import Hearing

    sample_rate = 16000
    bytes_per_sample = 2
    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=sample_rate,
        bytes_per_sample=bytes_per_sample,
        use_asr=False,
        record=False,
        debug=False,
    )
    vad = VADModule(
        chunk_time=args.chunk_time,
        onset_time=0.2,
        turn_offset=0.75,
        ipu_offset=0.3,
        fast_offset=0.1,
        prob_thresh=0.9,
    )

    vad.event_subscribe(vad.EVENT_VAD_TURN_CHANGE, vad.debug_callback)
    vad.event_subscribe(vad.EVENT_VAD_IPU_CHANGE, vad.debug_callback)
    vad.event_subscribe(vad.EVENT_VAD_FAST_CHANGE, vad.debug_callback)

    # Connect Components
    hearing.vad_frames.subscribe(vad)

    # run
    hearing.run_components()
    vad.run()
    print("VAD")
    try:
        input()
    except KeyboardInterrupt:
        pass
    hearing.stop_components()
    vad.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VAD")
    parser.add_argument("--onset", type=float, default=0.5)
    parser.add_argument("--offset", type=float, default=0.5)
    parser.add_argument("--chunk_time", type=float, default=0.01)
    parser.add_argument("--test", type=str, default="vadmodule")
    args = parser.parse_args()

    if args.test == "vadmodule":
        test_vad_module(args)
    elif args.test == "vad_frames":
        test_vad_frames(args)
    elif args.test == "vad":
        test_vad(args)
    else:
        raise NotImplementedError("Please choose --test [vadmodule, vad_frames, vad]")
