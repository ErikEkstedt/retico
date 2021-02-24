from argparse import ArgumentParser
from os.path import join, exists
from os import makedirs
import subprocess
from datetime import datetime

from retico.agent import Hearing, Speech
from retico.agent.CNS import CNS
from retico.agent.dm.dm import DM, DM_LM, DMExperiment
from retico.agent.policies import (
    FC_Simple,
    FC_Baseline,
    FC_EOT,
    FC_Predict,
    # CNS_Continuous,
)
from retico.agent.vad import VADModule

# from retico.agent.utils import create_session_dir, write_json
from retico.agent.utils import write_json


"""
Experiment


* 3 different dialogs with 3 different policies
* 1 Folder for each user with subfolders for each policy
* The researcher needs to start each task/policy and provide a root dir

root/
    ├── baseline
    ├── eot
    └── prediction
        ├── hearing/
        ├── speech/
        ├── tts/
        ├── annotation.json
        ├── dialog.json
        ├── dialog.wav
        └── hparams.json
"""


class Agent:
    POLICIES = ["baseline", "eot", "prediction", "simple"]

    def __init__(
        self,
        policy="baseline",
        dm_type="experiment",
        task="exercise",
        chit_chat_prob=0.0,
        short_heuristic_cutoff=3,
        chunk_time=0.01,
        sample_rate=48000,
        bytes_per_sample=2,
        speech_chunk_time=0.1,
        speech_sample_rate=48000,
        fallback_duration=2,
        backchannel_prob=0.5,
        trp=0.1,
        record=True,
        bypass=False,
        verbose=False,
        show_dialog=False,
        tts_cache_path="/home/erik/.cache/agent/tts",
        root="/home/erik/.cache/agent",
    ):
        policy = policy.lower()
        assert (
            policy in self.POLICIES
        ), f"Policy ({policy}) is not implemented. Please choose {self.POLICIES}"

        self.policy = policy
        self.dm_type = dm_type
        self.task = task
        self.chunk_time = chunk_time
        self.sample_rate = sample_rate
        self.bytes_per_sample = bytes_per_sample
        self.speech_chunk_time = speech_chunk_time
        self.speech_sample_rate = speech_sample_rate
        self.fallback_duration = fallback_duration
        self.backchannel_prob = backchannel_prob
        self.trp = trp
        self.record = record
        self.verbose = verbose
        self.bypass = bypass
        self.root = root

        # ---------------------------------------------
        makedirs(self.root, exist_ok=True)
        self.session_dir = join(self.root, policy)
        makedirs(self.session_dir)
        # self.session_dir = create_session_dir(root)
        print(self.session_dir)
        self.hearing = Hearing(
            chunk_time=chunk_time,
            sample_rate=sample_rate,
            bytes_per_sample=bytes_per_sample,
            use_asr=True,
            record=record,
            cache_dir=self.session_dir,
            bypass=bypass,
            debug=False,
        )
        self.speech = Speech(
            chunk_time=speech_chunk_time,
            sample_rate=speech_sample_rate,
            bytes_per_sample=bytes_per_sample,
            tts_client="amazon",
            output_word_times=True,
            bypass=bypass,
            record=record,
            cache_dir=tts_cache_path,
            result_dir=self.session_dir,
            debug=False,
        )

        if dm_type.startswith("experiment"):
            print("DM: EXPERIMENT")
            print("TASK: ", task)
            self.dm = DMExperiment(
                task=task,
                chit_chat_prob=chit_chat_prob,
                short_heuristic_cutoff=short_heuristic_cutoff,
            )
        elif dm_type.startswith("gen"):
            print("DM: GENERATION")
            self.dm = DM_LM()
        elif dm_type.startswith("quest"):
            print("DM: QUESTIONS")
            self.dm = DM()
        else:
            self.dm = None

        self.vad = VADModule(
            chunk_time=chunk_time,
            onset_time=0.15,
            turn_offset=0.75,
            ipu_offset=0.2,
            fast_offset=0.1,
            prob_thresh=0.9,
        )

        self.cns = CNS(verbose=verbose)

        if policy == "simple":
            print("Policy: Simple")
            self.fcortex = FC_Simple(
                dm=self.dm,
                central_nervous_system=self.cns,
                fallback_duration=fallback_duration,
                verbose=verbose,
            )
        elif policy == "prediction":
            print("Policy: PREDICTION")
            self.fcortex = FC_Predict(
                dm=self.dm,
                central_nervous_system=self.cns,
                fallback_duration=fallback_duration,
                trp_threshold=trp,
                verbose=verbose,
            )
        elif policy == "eot":
            print("Policy: EOT")
            self.fcortex = FC_EOT(
                dm=self.dm,
                central_nervous_system=self.cns,
                trp_threshold=trp,
                fallback_duration=fallback_duration,
                verbose=verbose,
            )
        else:
            print("Policy: BASELINE")
            self.fcortex = FC_Baseline(
                dm=self.dm,
                central_nervous_system=self.cns,
                fallback_duration=fallback_duration,
                verbose=verbose,
            )

        self.cns.subscribe(self.speech.tts)
        self.hearing.asr.subscribe(self.cns)
        self.hearing.vad_frames.subscribe(self.vad)
        self.speech.audio_dispatcher.subscribe(self.cns)

        self.vad.event_subscribe(self.vad.EVENT_VAD_IPU_CHANGE, self.cns.vad_callback)
        self.vad.event_subscribe(self.vad.EVENT_VAD_TURN_CHANGE, self.cns.vad_callback)

        self.save_hyperparameters()

    def save_hyperparameters(self):
        hparams = {
            "policy": self.policy,
            "dm_type": self.dm_type,
            "task": self.task,
            "chunk_time": self.chunk_time,
            "sample_rate": self.sample_rate,
            "bytes_per_sample": self.bytes_per_sample,
            "speech_chunk_time": self.speech_chunk_time,
            "speech_sample_rate": self.speech_sample_rate,
            "fallback_duration": self.fallback_duration,
            "backchannel_prob": self.backchannel_prob,
            "trp": self.trp,
            "verbose": self.verbose,
            "bypass": self.bypass,
            "date": datetime.now().strftime("%Y-%m-%d_%H:%M"),
        }

        savepath = join(self.session_dir, "hparams.json")
        write_json(hparams, savepath)
        print("Saved hparams -> ", savepath)

    def join_audio(self):
        user_wav = join(self.session_dir, "hearing", "user_audio.wav")
        agent_wav = join(self.session_dir, "speech", "agent_audio.wav")

        assert exists(agent_wav), f"did not find agent recording: {agent_wav}"
        assert exists(user_wav), f"did not find user recording: {user_wav}"

        comb_wav = join(self.session_dir, "dialog.wav")

        cmd = ["sox", "-M", agent_wav, user_wav, comb_wav]
        subprocess.call(cmd)
        print("Joined audio -> ", comb_wav)

    @staticmethod
    def add_agent_args(parent_parser):
        parser = ArgumentParser(parents=[parent_parser], add_help=False)
        parser.add_argument("--policy", type=str, default="baseline")
        parser.add_argument("--dm_type", type=str, default="experiment")

        parser = DMExperiment.add_dm_args(parser)

        parser.add_argument("--root", type=str, default="/tmp/Agent")
        parser.add_argument("--chunk_time", type=float, default=0.01)
        parser.add_argument("--sample_rate", type=int, default=48000)
        parser.add_argument("--speech_chunk_time", type=float, default=0.1)
        parser.add_argument("--speech_sample_rate", type=int, default=48000)
        parser.add_argument("--bytes_per_sample", type=int, default=2)
        parser.add_argument("--trp", type=float, default=0.1)
        parser.add_argument("--fallback_duration", type=float, default=3)
        parser.add_argument("--backchannel_prob", type=float, default=0.5)
        parser.add_argument("--bypass", action="store_true")
        parser.add_argument("--verbose", action="store_true")
        return parser

    def start(self):
        self.cns.run()
        self.vad.run()
        self.hearing.run()
        self.speech.run()
        self.fcortex.start_loop()

        input("DIALOG\n")

        self.hearing.stop()
        self.speech.stop()
        # self.speech.tts.shutdown()
        self.vad.stop()
        self.cns.stop()
        self.cns.save(join(self.session_dir, "dialog.json"))
        # self.cns.memory.save(join(self.session_dir, "dialog.json"))
        self.join_audio()
        self.hearing.asr.active = False
        self.fcortex.dialog_ended = True


if __name__ == "__main__":

    parser = ArgumentParser(description="DialogState")
    parser = Agent.add_agent_args(parser)
    args = parser.parse_args()

    # args.root = "/home/erik/Documents/Agent"
    # args.policy = 'eot'
    # args.task = 'food'

    agent = Agent(
        policy=args.policy,
        dm_type=args.dm_type,
        task=args.task,
        chit_chat_prob=args.chit_chat_prob,
        short_heuristic_cutoff=args.short_heuristic_cutoff,
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        speech_chunk_time=args.speech_chunk_time,
        speech_sample_rate=args.speech_sample_rate,
        fallback_duration=args.fallback_duration,
        backchannel_prob=args.backchannel_prob,
        trp=args.trp,
        verbose=args.verbose,
        bypass=args.bypass,
        root=args.root,
    )

    agent.start()
