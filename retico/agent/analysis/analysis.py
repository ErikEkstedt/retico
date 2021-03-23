from argparse import ArgumentParser
from os.path import join, exists, isdir, basename
from os import listdir
from glob import glob
from tqdm import tqdm

import matplotlib.pyplot as plt
import numpy as np

import torch
from torchaudio.transforms import Resample


from retico.agent.analysis.utils import load_interaction, read_audio
from retico.agent.utils import read_json


POLICIES = ["baseline", "baselinevad", "prediction"]


class Analysis:
    @staticmethod
    def tfo(interaction_dir=None, data=None):
        if data is None:
            data = load_interaction(interaction_dir)
        return {
            "agent": find_agent_offsets(data["dialog"]),
            "user": find_user_offsets(data["dialog"]),
        }

    @staticmethod
    def get_turns(interaction_dir=None, data=None):
        if data is None:
            data = load_interaction(interaction_dir)
        dialog = data["dialog"]
        return {"turns": dialog["turns"]}

    @staticmethod
    def get_omitted_turns(interaction_dir=None, data=None):
        if data is None:
            data = load_interaction(interaction_dir)
        dialog = data["dialog"]
        omitted_turns = []
        if "omitted_agent_turns" in dialog:
            for turn in dialog["omitted_agent_turns"]:
                turn["diff"] = turn["end_time"] - turn["start_time"]
                omitted_turns.append(turn)
        return {"omitted_turns": omitted_turns}

    @staticmethod
    def fallbacks(interaction_dir=None, data=None):
        if data is None:
            data = load_interaction(interaction_dir)

        dialog = data["dialog"]
        fallbacks = []
        for turn in dialog["turns"]:
            if "fallback" in turn:
                if turn["fallback"]:
                    fallbacks.append(turn["end_time"])
        return {"fallbacks": fallbacks}

    @staticmethod
    def responsiveness_and_interruption(interaction_dir=None, data=None, p_time=0.2):
        if data is None:
            data = load_interaction(interaction_dir)
        dialog = data["dialog"]
        pause_duration, shift_duration = get_interval_durations(dialog)
        interruptions = get_interruptions(data=data)

        N = len(pause_duration) + len(shift_duration)
        target_err = interruptions / N
        target_time = torch.tensor(shift_duration).mean().item()
        target_time_med = torch.tensor(shift_duration).median().item()

        p = torch.tensor(pause_duration)
        p2 = p[p >= p_time]
        N2 = p2.nelement() + len(shift_duration)
        te2 = interruptions / N2
        return {
            "interruptions": interruptions,
            "pauses": pause_duration,
            "shifts": shift_duration,
            "error": target_err,
            "time_mean": target_time,
            "time_median": target_time_med,
            f"error_over_{int(p_time*1000)}": te2,
            "Np": N2,
        }

    @staticmethod
    def trp_info(interaction_dir=None, data=None):
        if data is None:
            data = load_interaction(interaction_dir)
        dialog = data["dialog"]
        all_trps = []
        n_user_turns = 0
        n_agent_realized_turns = 0
        agent_aborted = 0
        for turn in dialog["turns"]:
            if turn["name"] == "agent":
                n_agent_realized_turns += 1
                if turn["interrupted"]:
                    agent_aborted += 1
            else:
                n_user_turns += 1
                if "all_trps" in turn:
                    for trp in turn["all_trps"]:
                        all_trps.append(trp["trp"])
        r = round(agent_aborted / n_agent_realized_turns, 2)

        omitted_turns = Analysis.get_omitted_turns(data=data)

        return {
            "trp": all_trps,
            "user_turns": n_user_turns,
            "agent_turns": n_agent_realized_turns,
            "agent_aborted": agent_aborted,
            "agent_abort_ratio": r,
            "omitted_turns": omitted_turns["omitted_turns"],
        }

    @staticmethod
    def annotation(interaction_dir=None, data=None):
        if data is None:
            data = load_interaction(interaction_dir)
        ret = {"grades": {}, "anno": {}}
        if data["anno"] is not None:
            if "grades" in data["anno"]:
                for grade, val in data["anno"]["grades"].items():
                    ret["grades"][grade] = int(val)

            if "anno" in data["anno"]:
                for tmp_anno in data["anno"]["anno"]:
                    event = tmp_anno["anno"]
                    if event not in ret["anno"]:
                        ret["anno"][event] = 0
                    ret["anno"][event] += 1
        return ret

    @staticmethod
    def agent_possible_onset_events(interaction_dir=None, data=None):
        if data is None:
            data = load_interaction(interaction_dir)

        dialog = data["dialog"]
        off, _ = torch.tensor(dialog["vad_ipu_off"]).sort()
        on, _ = torch.tensor(dialog["vad_ipu_on"]).sort()
        agent_on, _ = torch.tensor(dialog["agent_turn_on"]).sort()

        events = {
            "pauses": {"duration": [], "start": []},
            "shifts": {"duration": [], "start": []},
        }
        for v in off:
            v = v.item()

            vad_off = None
            next_agent = None
            vads_left = on[on > v]
            if len(vads_left) > 0:
                vad_off = vads_left[0].item()
            aon = agent_on[agent_on > v]
            if len(aon) > 0:
                next_agent = aon[0].item()

            ##############################################
            if vad_off is None and next_agent is None:
                pass
            elif vad_off is None:
                events["shifts"]["duration"].append(next_agent - v)
                events["shifts"]["start"].append(v)
            elif next_agent is None:
                events["pauses"]["duration"].append(vad_off - v)
                events["pauses"]["start"].append(v)
            else:
                if vad_off < next_agent:
                    events["pauses"]["duration"].append(vad_off - v)
                    events["pauses"]["start"].append(v)
                else:
                    events["shifts"]["duration"].append(next_agent - v)
                    events["shifts"]["start"].append(v)
        return events

    @staticmethod
    def aggregate(experiment_dir):
        experiment = get_experiment_data(experiment_dir)
        # jsonify
        for policy, poldata in experiment.items():
            for name in ["agent", "user"]:
                a = poldata["tfo"][name].t().tolist()
                poldata["tfo"][name] = {"start": a[0], "end": a[1], "duration": a[2]}

            # extract only mean & std
            for grade, v in poldata["grades"].items():
                poldata["grades"][grade] = {
                    "mean": torch.tensor(v).float().mean().item(),
                    "std": torch.tensor(v).float().std().item(),
                }

            # sum anno
            for anno, v in poldata["anno"].items():
                poldata["anno"][anno] = {
                    "mean": torch.tensor(v).float().mean().item(),
                    "std": torch.tensor(v).float().std().item(),
                }

            poldata["anno"]["missed_eot"] = poldata["anno"]["missed-eot"]
            poldata["anno"].pop("missed-eot")
        return experiment


def get_args():
    parser = ArgumentParser()
    parser.add_argument("--root")
    parser.add_argument("--bins", type=int, default=25)
    parser.add_argument("--normalize", action="store_true")
    parser.add_argument("--filename", type=str, default="/tmp/test_result.json")
    return parser.parse_args()


def get_interaction_data(interaction_dir, include_audio=False, include_dialog=False):
    data = load_interaction(interaction_dir)

    interaction_data = {
        "vad": {
            "on": data["dialog"]["vad_ipu_on"],
            "off": data["dialog"]["vad_ipu_off"],
        },
        "asr": {"on": data["dialog"]["asr_on"], "off": data["dialog"]["asr_off"]},
        "tfo": Analysis.tfo(data=data),
        "trp": [],
        "interruption": [],
        "fallback": Analysis.fallbacks(data=data)["fallbacks"],
        "turn_starts": {
            "agent": [],
            "user": [],
        },
        "turn_ends": {
            "agent": [],
            "user": [],
        },
        "grades": {},
        "anno": {"interruption": 0, "missed-eot": 0},
    }

    for turn in data["dialog"]["turns"]:
        interaction_data["turn_starts"][turn["name"]].append(turn["start_time"])
        interaction_data["turn_ends"][turn["name"]].append(turn["end_time"])
        if turn["name"] == "agent":
            if turn["interrupted"]:
                interaction_data["interruption"].append(turn["end_time"])
        else:
            interaction_data["trp"] += turn["all_trps"]

    if data["anno"] is not None:
        if "grades" in data["anno"]:
            for grade, val in data["anno"]["grades"].items():
                interaction_data["grades"][grade] = int(val)

        if "anno" in data["anno"]:
            for tmp_anno in data["anno"]["anno"]:
                event = tmp_anno["anno"]
                if event not in interaction_data["anno"]:
                    interaction_data["anno"][event] = 0
                interaction_data["anno"][event] += 1

    if basename(interaction_dir) == "baseline":
        interaction_data["pauses"] = get_pauses(data["dialog"])

    if include_audio:
        interaction_data["audio"] = data["audio"]

    if include_dialog:
        interaction_data["dialog"] = data["dialog"]

    return interaction_data


def get_session_data(session_dir):
    session = {}
    for policy in POLICIES:
        interaction_dir = join(session_dir, policy)
        if exists(interaction_dir):
            session[policy] = get_interaction_data(interaction_dir)
    return session


def get_experiment_data(experiment_dir):
    experiment = {}
    for session_dir in tqdm(listdir(experiment_dir)):
        session_dir = join(experiment_dir, session_dir)
        if isdir(session_dir):
            session = get_session_data(session_dir)
            for policy, data in session.items():
                if policy not in experiment:
                    experiment[policy] = {}

                # Grades/Score
                if "grades" in data:
                    if "grades" not in experiment[policy]:
                        experiment[policy]["grades"] = {}
                    for g, score in data["grades"].items():
                        if g not in experiment[policy]["grades"]:
                            experiment[policy]["grades"][g] = []
                        experiment[policy]["grades"][g].append(score)

                # Annotation
                if "anno" in data:
                    if "anno" not in experiment[policy]:
                        experiment[policy]["anno"] = {}
                    for anno, count in data["anno"].items():
                        if anno not in experiment[policy]["anno"]:
                            experiment[policy]["anno"][anno] = []
                        experiment[policy]["anno"][anno].append(count)

                # TFO
                if "tfo" in data:
                    if "tfo" not in experiment[policy]:
                        experiment[policy]["tfo"] = {}
                    for name, start_end_duration in data["tfo"].items():
                        if name not in experiment[policy]["tfo"]:
                            experiment[policy]["tfo"][name] = []
                        experiment[policy]["tfo"][name].append(start_end_duration)

    for policy in experiment.keys():
        if policy == "pauses_baseline":
            experiment["pauses_baseline"] = torch.cat(experiment["pauses_baseline"])
        else:
            for name, tfo in experiment[policy]["tfo"].items():
                experiment[policy]["tfo"][name] = torch.cat(tfo)

    return experiment


############################################
# Interaction


def tfo_interaction(interaction_dir):
    data = load_interaction(interaction_dir)
    return {
        "agent": find_agent_offsets(data["dialog"]),
        "user": find_user_offsets(data["dialog"]),
    }


############################################
# TFO
def find_agent_offsets(dialog):
    offsets = []
    ipu_off = torch.tensor(dialog["vad_ipu_off"])
    for i, turn in enumerate(dialog["turns"][1:]):
        name = turn["name"]
        if name == "agent" and dialog["turns"][i + 1] != "agent":
            if not turn["interrupted"]:
                agent_start = turn["start_time"]
                user_end = ipu_off[ipu_off < agent_start]
                if len(user_end) > 0:
                    user_end = user_end[-1]
                    offsets.append([user_end, agent_start, agent_start - user_end])
    offsets = torch.tensor(offsets)  # N, 3
    return offsets


def find_user_offsets(dialog):
    offsets = []
    ipu_on = torch.tensor(dialog["vad_ipu_on"])
    for i, turn in enumerate(dialog["turns"][:-1]):
        name = turn["name"]
        if name == "agent" and dialog["turns"][i + 1] != "agent":
            if not turn["interrupted"]:
                agent_end = turn["end_time"]
                user_start = ipu_on[ipu_on > agent_end]
                if len(user_start) > 0:
                    user_start = user_start[0]
                    offsets.append([agent_end, user_start, user_start - agent_end])
    offsets = torch.tensor(offsets)  # N, 2
    return offsets


# Plots
def ax_hist(
    x, ax, normalize=True, bins=25, alpha=0.2, range=(0, 2), label=None, color=None
):
    weight = torch.ones_like(x)
    if normalize:
        weight /= weight.nelement()
    a = ax.hist(
        x.view(1, -1),
        bins=bins,
        range=range,
        alpha=alpha,
        label=label,
        color=color,
        weights=weight.view(1, -1),
    )
    return a


def ax_interval_fill(
    ax, starts, ends, s=None, e=None, ymin=0, ymax=1, color="g", alpha=0.2
):
    ys = np.array([ymax, ymax, ymin, ymin])
    for start, end in zip(starts, ends):
        if s is not None:
            if start > s and end <= e:
                ax.fill(
                    np.array([start, end, end, start]), ys, color=color, alpha=alpha
                )
        else:
            ax.fill(np.array([start, end, end, start]), ys, color=color, alpha=alpha)


def fig_tfo_intervals(
    waveform,
    sr,
    user_offsets,
    agent_offsets,
    offset=0,
    figsize=(16, 4),
    plot=False,
    resample_hz=8000,
):
    duration = waveform.shape[-1] / sr
    N = waveform.shape[-1]

    if sr > resample_hz:
        waveform = Resample(sr, resample_hz)(waveform)
        print(f"{N} -> {waveform.shape[-1]}")
        N = waveform.shape[-1]

    usta = (user_offsets[:, 0] + offset) * N / duration
    uend = (user_offsets[:, 1] + offset) * N / duration
    asta = (agent_offsets[:, 0] - offset) * N / duration
    aend = (agent_offsets[:, 1] - offset) * N / duration

    fig, ax = plt.subplots(2, 1, figsize=figsize, sharex=True, sharey=True)
    # waveform
    ax[0].plot(waveform[0], label="agent")
    ax[1].plot(waveform[1], label="user")

    # VAD
    ax_interval_fill(ax[0], asta, aend, ymin=-0.4, ymax=0.4, alpha=0.1, color="g")
    ax_interval_fill(ax[0], usta, uend, ymin=-0.4, ymax=0.4, alpha=0.1, color="r")
    ax_interval_fill(ax[1], usta, uend, ymin=-0.4, ymax=0.4, alpha=0.1, color="r")
    ax_interval_fill(ax[1], asta, aend, ymin=-0.4, ymax=0.4, alpha=0.1, color="g")
    if plot:
        plt.pause(0.01)
    return fig, ax


def histogram_offsets(
    tfos, bins=25, range=(0, 4), alpha=0.2, normalize=True, plot=True
):
    colors = ["b", "g", "r"]
    fig, ax = plt.subplots(1, 1, figsize=(9, 6))
    for c, (k, v) in zip(colors, tfos.items()):
        v = torch.cat(v)
        m = round(v.mean().item(), 2)
        s = round(v.std().item(), 2)
        label = f"{k} {m}({s})"

        weight = torch.ones_like(v)
        if normalize:
            weight /= v.nelement()
        a = ax.hist(
            v.view(1, -1),
            bins=bins,
            range=range,
            alpha=alpha,
            label=label,
            color=c,
            weights=weight.view(1, -1),
        )
    ax.legend()
    ax.set_xlabel("Turn Floor Offset")
    ax.set_ylabel("N")
    plt.tight_layout()
    if plot:
        plt.pause(0.1)
    return fig, ax


def plot_experiment_tfo(experiment, alpha=0.4, plot=True):
    color = {"baseline": "b", "baselinevad": "r", "prediction": "g"}
    fig, ax = plt.subplots(2, 1, figsize=(12, 5), sharex=True)
    fig.suptitle("TFO")
    for policy in experiment.keys():
        if policy == "pauses_baseline":
            continue
        _ = ax_hist(
            experiment[policy]["tfo"]["user"][:, -1],
            ax=ax[0],
            label=f"user-{policy}",
            bins=30,
            alpha=alpha,
            color=color[policy],
        )
        _ = ax_hist(
            experiment[policy]["tfo"]["agent"][:, -1],
            ax=ax[1],
            label=f"agent-{policy}",
            bins=30,
            alpha=alpha,
            color=color[policy],
        )
        # print(policy, experiment[policy]['anno'])
    ax[0].legend()
    ax[1].legend()
    ax[1].set_xlabel("Time, s")
    if plot:
        plt.pause(0.1)
    return fig, ax


def plot_experiment_grades(experiment, alpha=0.4, plot=True):
    c = {"baseline": "b", "baselinevad": "r", "prediction": "g"}
    x = {"responsiveness": 0, "natural": 2, "enjoyment": 4}
    step = 0.5
    shift = {"baseline": -step, "baselinevad": 0, "prediction": step}
    fig, ax = plt.subplots(1, 1, figsize=(9, 6))
    for policy in experiment.keys():
        if policy == "pauses_baseline":
            continue
        # print(experiment[policy]['grades'])
        for grade, score in experiment[policy]["grades"].items():
            m = round(torch.Tensor(score).mean().item(), 2)
            if grade == "natural":
                ax.bar(
                    x[grade] + shift[policy],
                    m,
                    width=step,
                    color=c[policy],
                    label=policy,
                    alpha=alpha,
                )
            else:
                ax.bar(
                    x[grade] + shift[policy],
                    m,
                    width=step,
                    color=c[policy],
                    alpha=alpha,
                )
    xnames = [k for k in x.keys()]
    xx = [k for _, k in x.items()]
    ax.set_ylim([1, 5])
    ax.set_xticks(xx)
    ax.set_xticklabels(xnames)
    ax.legend()
    # ax.legend(['baseline', 'baselinevad', 'prediction'], labelcolor=[col for _, col in c.items()])
    if plot:
        plt.pause(0.1)
    return fig, ax


def plot_experiment_anno(experiment, alpha=0.4, plot=True):
    c = {"baseline": "b", "baselinevad": "r", "prediction": "g"}
    x = {"interruption": 0, "missed-eot": 2}
    step = 0.5
    shift = {"baseline": -step, "baselinevad": 0, "prediction": step}
    fig, ax = plt.subplots(1, 1, figsize=(9, 6))
    for policy in experiment.keys():
        if policy == "pauses_baseline":
            continue
        # print(experiment[policy]['grades'])
        for grade, score in experiment[policy]["anno"].items():
            m = round(torch.Tensor(score).mean().item(), 2)
            if grade == "interruption":
                ax.bar(
                    x[grade] + shift[policy],
                    m,
                    width=step,
                    color=c[policy],
                    label=policy,
                    alpha=alpha,
                )
            else:
                ax.bar(
                    x[grade] + shift[policy],
                    m,
                    width=step,
                    color=c[policy],
                    alpha=alpha,
                )
    xnames = [k for k in x.keys()]
    xx = [k for _, k in x.items()]
    ax.set_xticks(xx)
    ax.set_xticklabels(xnames)
    ax.legend()
    # ax.legend(['baseline', 'baselinevad', 'prediction'], labelcolor=[col for _, col in c.items()])
    if plot:
        plt.pause(0.1)
    return fig, ax


def get_pauses(dialog):
    starts = []
    ends = []
    for turn in dialog["turns"]:
        if turn["name"] == "user":
            starts.append(turn["start_time"])
            ends.append(turn["end_time"])
    user_turns = torch.Tensor([starts, ends]).t()

    vad = torch.Tensor([dialog["vad_ipu_on"], dialog["vad_ipu_off"]])
    all_diff = vad[0, 1:] - vad[1, :-1]

    pauses = []
    for start, diff in zip(vad[1, :-1], all_diff):
        for ut in user_turns:
            end = start + diff
            if ut[0] <= end <= ut[1] and ut[0] <= start <= ut[1]:
                pauses.append(diff.item())
    return pauses


def plot_pauses(
    pauses,
    shifts,
    interrupts=0,
    target_pauses=None,
    target_shifts=None,
    target_err=None,
    target_time=None,
    baseline_err=None,
    baseline_time=None,
    target_time_offset=0,
    plot=True,
):
    N = 0
    if isinstance(pauses, list):
        pauses = torch.tensor(pauses)
    N += pauses.nelement()

    if shifts is not None:
        if isinstance(shifts, list):
            shifts = torch.tensor(shifts)
        N += shifts.nelement()

    nplots = 2
    height = 6
    if target_pauses is not None:
        nplots += 1
        height += 3
    fig, ax = plt.subplots(nplots, 1, figsize=(9, height), sharex=True)
    _ = ax_hist(pauses, ax=ax[0], label="baseline pauses", bins=30, normalize=True)

    if shifts is not None:
        _ = ax_hist(
            shifts,
            ax=ax[0],
            label="baseline shifts",
            bins=30,
            normalize=True,
            color="r",
        )

    if target_pauses is not None:
        _ = ax_hist(
            target_pauses,
            ax=ax[1],
            label="prediction pauses",
            bins=30,
            normalize=True,
            color="b",
        )
        ax[1].set_ylabel("%")

    if target_shifts is not None:
        _ = ax_hist(
            target_shifts,
            ax=ax[1],
            label="prediction shifts",
            bins=30,
            normalize=True,
            color="r",
        )
    if target_pauses is not None:
        ax[1].legend()

    ax[0].legend()
    ax[0].set_title(
        """All user VAD-ends are counted.  Those where a shift occured are never an interrupt.  Given a cutoff 
        we assume the dialog is stationary and count how many interruptions there would be.
        The actual amounts of interruptions are accounted for by adding to the cutoff interrupts.
        """
    )
    ax[0].set_ylabel("%")

    cut_ins = []
    cut_off = torch.linspace(0.1, 2.0, 20)
    for co in cut_off:
        # cut_ins.append((pauses >= co).sum() / len(pauses)
        # cut_ins.append((pauses >= co).sum() / N)
        cut_ins.append(((pauses >= co).sum() + interrupts) / N)
    ax[-1].plot(cut_off, cut_ins, label="calculated baseline")

    if target_err is not None and target_time is not None:
        ax[-1].scatter(
            target_time,
            target_err,
            label=f"prediction ({round(target_time,2)}, {round(target_err,2)})",
            color="r",
        )
        ax[-1].hlines(
            target_err,
            xmin=0,
            xmax=target_time,
            linestyle="dashed",
            color="r",
            linewidth=1,
        )
        ax[-1].vlines(
            target_time,
            ymin=0,
            ymax=target_err,
            linestyle="dashed",
            color="r",
            linewidth=1,
        )
        ax[-1].scatter(
            target_time + target_time_offset,
            target_err,
            label=f"prediction + audio-silence ({round(target_time,2)+target_time_offset}, {round(target_err,2)})",
            color="#ff7f0e",
        )
        ax[-1].hlines(
            target_err,
            xmin=0,
            xmax=target_time + target_time_offset,
            linestyle="dashed",
            color="r",
            linewidth=0.5,
        )
        ax[-1].vlines(
            target_time + target_time_offset,
            ymin=0,
            ymax=target_err,
            linestyle="dashed",
            color="r",
            linewidth=0.5,
        )

    if baseline_err is not None and baseline_time is not None:
        ax[-1].scatter(
            baseline_time,
            baseline_err,
            label=f"baseline ({round(baseline_time,2)}, {round(baseline_err,2)})",
            color="b",
        )
        ax[-1].hlines(
            baseline_err,
            xmin=0,
            xmax=baseline_time,
            linestyle="dashed",
            color="b",
            linewidth=1,
        )
        ax[-1].vlines(
            baseline_time,
            ymin=0,
            ymax=baseline_err,
            linestyle="dashed",
            color="b",
            linewidth=1,
        )

    ax[-1].set_xlim([0, 2.0])
    ax[-1].set_ylim([0, 0.8])
    ax[-1].legend()
    ax[-1].set_xlabel("cut off time, s")
    ax[-1].set_ylabel("%")
    # plt.tight_layout(rect=(0.02, 0.02, 0.98, 0.95))
    plt.tight_layout()
    if plot:
        plt.pause(0.1)
    return fig, ax


def get_interval_durations(dialog):
    off, _ = torch.tensor(dialog["vad_ipu_off"]).sort()
    on, _ = torch.tensor(dialog["vad_ipu_on"]).sort()
    agent_on, _ = torch.tensor(dialog["agent_turn_on"]).sort()

    pause_duration = []
    shift_duration = []
    for v in off:
        vad_off = None
        next_agent = None
        vads_left = on[on > v]
        if len(vads_left) > 0:
            vad_off = vads_left[0].item()
        aon = agent_on[agent_on > v]
        if len(aon) > 0:
            next_agent = aon[0]
        ##############################################
        if vad_off is None and next_agent is None:
            pass
        elif vad_off is None:
            shift_duration.append((next_agent - v).item())
        elif next_agent is None:
            pause_duration.append((vad_off - v).item())
        else:
            if vad_off < next_agent:
                pause_duration.append((vad_off - v).item())
            else:
                shift_duration.append((next_agent - v).item())
    return pause_duration, shift_duration


def get_interruptions(interaction_dir=None, data=None):
    if data is None:
        data = load_interaction(interaction_dir)
    dialog = data["dialog"]
    interruptions = 0
    for turn in dialog["turns"]:
        if "interrupted" in turn:
            if turn["interrupted"]:
                interruptions += 1
    return interruptions


def interruption_time_data(root):
    pauses = []
    shifts = []
    prediction_shifts = []
    prediction_pauses = []
    prediction_interrupts = 0
    interrupts = 0
    for session in tqdm(listdir(root)):
        dirpath = join(root, session)
        if isdir(dirpath):
            for policy in listdir(dirpath):
                if not policy == "baselinevad":
                    polpath = join(dirpath, policy)
                    data = load_interaction(polpath)
                    dialog = data["dialog"]
                    pause_duration, shift_duration = get_interval_durations(dialog)
                    anpath = join(polpath, "annotation.json")
                    tmp_interrupts = 0
                    if exists(anpath):
                        anno = read_json(anpath)
                        for a in anno["anno"]:
                            if a["anno"] == "interruption":
                                tmp_interrupts += 1
                    if policy == "baseline":
                        pauses += pause_duration
                        shifts += shift_duration
                        interrupts += tmp_interrupts
                    else:
                        prediction_pauses += pause_duration
                        prediction_shifts += shift_duration
                        prediction_interrupts += tmp_interrupts

    prediction_pauses = torch.tensor(prediction_pauses)
    prediction_pauses = prediction_pauses[prediction_pauses < 5]
    prediction_shifts = torch.tensor(prediction_shifts)
    N = prediction_pauses.nelement() + prediction_shifts.nelement()
    target_err = prediction_interrupts / N
    target_time = prediction_shifts.mean().item()

    pauses = torch.tensor(pauses)
    pauses = pauses[pauses < 5]
    shifts = torch.tensor(shifts)
    N_baseline = pauses.nelement() + shifts.nelement()

    baseline_err = interrupts / N_baseline
    baseline_time = shifts.mean().item()
    return {
        "prediction": {
            "pauses": prediction_pauses,
            "shifts": prediction_shifts,
            "N": N,
            "err": target_err,
            "time": target_time,
            "interrupts": prediction_interrupts,
        },
        "baseline": {
            "pauses": pauses,
            "shifts": shifts,
            "N": N_baseline,
            "err": baseline_err,
            "time": baseline_time,
            "interrupts": interrupts,
        },
    }


def audio_diff(interaction_dir=None, data=None, thresh=0.04, plot=False):
    def t2s(t, sr):
        return int(t * sr)

    def s2t(s, sr):
        return round(s / sr, 3)

    if data is None:
        data = load_interaction(interaction_dir)

    dialog = data["dialog"]
    sr = data["audio"]["sample_rate"]
    waveform = data["audio"]["waveform"]

    lookahead = t2s(1, sr)  # lookahead samples

    if plot:
        fig, ax = plt.subplots(1, 1)

    audio_diff = []
    for turn in dialog["turns"]:
        if turn["name"] == "agent":
            if turn["interrupted"]:
                diff = turn["end_time"] - turn["start_time"]
            else:
                s = t2s(turn["start_time"], sr)
                wf = waveform[0, s : s + lookahead]
                w = wf.abs()
                w = torch.where(w > thresh)[0]
                if len(w) > 0:
                    w = w[0].item()
                    s = s2t(w, sr)
                    if s > 0.01:
                        audio_diff.append(s)

                        if plot:
                            ax.cla()
                            ax.plot(wf)
                            ax.vlines(w, ymin=-0.5, ymax=0.5)
                            plt.pause(0.001)
                            input()
    if plot:
        plt.close()
    return audio_diff


def experiment_audio_diff(experiment_dir):
    adiff = []
    for session in tqdm(listdir(experiment_dir)):
        session_path = join(experiment_dir, session)
        if isdir(session_path):
            for interaction in listdir(session_path):
                interaction_dir = join(session_path, interaction)
                if isdir(interaction_dir):
                    # adiff += audio_diff(interaction_dir, plot=True)
                    adiff += audio_diff(interaction_dir)

    median = round(torch.tensor(adiff).median().item(), 2)
    mean = round(torch.tensor(adiff).mean().item(), 2)
    print("mean: ", mean)
    print("median: ", median)
    fig, ax = plt.subplots(1, 1)
    weight = torch.ones_like(torch.tensor(adiff)).unsqueeze(0)
    weight /= weight.nelement()
    ax.hist(adiff, bins=10, weights=weight)
    ax.vlines([median, mean], ymin=0, ymax=1, color=["r", "b"])
    plt.pause(0.01)


def audio_diff_from_audio_files(root="/home/erik/.cache/agent/tts", thresh=0.05):
    def s2t(s, sr):
        return round(s / sr, 3)

    diffs = []
    for wavpath in glob(join(root, "*.wav")):
        d = read_audio(wavpath)
        w = torch.where(d["waveform"][0] > thresh)[0]
        if len(w) > 0:
            w = w[0].item()
            time = s2t(w, d["sample_rate"])
            diffs.append(time)
    diffs = torch.tensor(diffs)
    return {"mean": round(diffs.mean().item(), 3), "std": round(diffs.std().item(), 3)}


def single():
    # Experiment (multiple sessions)
    # experiment_dir = "/home/erik/projects/retico/retico/agent/data/experiment_test"
    # experiment_dir = "/home/erik/Experiments"
    experiment_dir = "/home/erik/ExperimentPreStudy"
    experiment = get_experiment_data(experiment_dir)

    fig, ax = plot_experiment_tfo(experiment)
    fig2, ax2 = plot_experiment_grades(experiment)
    fig3, ax3 = plot_experiment_anno(experiment)

    curve = interruption_time_data(experiment_dir)

    fig4, ax4 = plot_pauses(
        pauses=curve["baseline"]["pauses"],
        shifts=curve["baseline"]["shifts"],
        interrupts=curve["baseline"]["interrupts"],
        target_pauses=curve["prediction"]["pauses"],
        target_shifts=curve["prediction"]["shifts"],
        target_time=curve["prediction"]["time"],
        target_err=curve["prediction"]["err"],
        baseline_time=curve["baseline"]["time"],
        baseline_err=curve["baseline"]["err"],
        target_time_offset=0.25,
    )

    # N_tfo = experiment["prediction"]["tfo"]["agent"].shape[0]
    # sum(experiment["baseline"]["anno"]["interruption"])

    interaction_dir = "/home/erik/ExperimentPreStudy/session_1/prediction"

    tfo = Analysis.tfo(interaction_dir)
    anno = Analysis.annotation(interaction_dir)
    turn_opportunity = Analysis.agent_possible_onset_events(interaction_dir)
    trp_data = Analysis.trp_info(interaction_dir)
    # data = load_interaction(interaction_dir)
    # tfo = Analysis.tfo(data=data)
    # anno = Analysis.annotation(data=data)
    # turn_opportunity = Analysis.agent_possible_onset_events(data=data)
    # trp_data = Analysis.trp_info(data=data)

    # Audio time
    # Where are we interrupted? time from turn-start to interrupt?
    # How long does it take to hear voice  from the system relative turn-start?
    data = load_interaction(interaction_dir)
    dialog = data["dialog"]

    waveform = data["audio"]["waveform"]
    sr = data["audio"]["sample_rate"]

    adiff = audio_diff(interaction_dir)
    avg_diff = torch.tensor(adiff).mean().item()
    print("avg diff: ", avg_diff)

    # experiment_dir = "/home/erik/ExperimentPreStudy"
    experiment_dir = "/home/erik/Experiments2/hej"
    experiment_audio_diff(experiment_dir)

    data = get_interaction_data(interaction_dir)
    print(data.keys())

    diff = audio_diff_from_audio_files()

    interaction_dir = "/home/erik/ExperimentsDebug/session_4/prediction"

    res = responsiveness_and_interruption(interaction_dir, p_time=0.4)

    print(len(res["pauses"]) + len(res["shifts"]))


if __name__ == "__main__":
    args = get_args()
    args.root = "/home/erik/ExperimentPreStudy"

    experiment = get_experiment_data(args.root)

    fig, ax = plot_experiment_tfo(experiment, plot=False)
    fig2, ax2 = plot_experiment_grades(experiment, plot=False)
    fig3, ax3 = plot_experiment_anno(experiment, plot=False)
    plt.show()
