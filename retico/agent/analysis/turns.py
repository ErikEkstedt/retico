from argparse import ArgumentParser
import requests
import json
import re

import torch
import torchaudio
import torchaudio.transforms as AT
import torchaudio.functional as AF

import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import numpy as np

import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

from retico.agent.analysis.utils import load_dialog_data
from retico.agent.utils import clean_whitespace


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])


def time_to_samples(t, sr):
    return int(t * sr)


def get_turn(turn_index, pre_pad, post_pad, turns, waveform, sr):
    turn = turns[turn_index]
    wf = waveform[
        :,
        time_to_samples(turn["start_time"], sr)
        - time_to_samples(pre_pad, sr) : time_to_samples(turn["end_time"], sr)
        + time_to_samples(post_pad, sr),
    ]
    channel = 1 if turn["name"] == "user" else 0
    x = wf[channel].unsqueeze(0)
    features = extract_features(x, sr)

    features["statistics"] = {
        "n_words": len(turn["utterance"].split()),
        "duration": round(turn["end_time"] - turn["start_time"], 2),
        "sample_rate": sr,
    }

    return turn, features


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


def get_figure(features, feature="Waveform"):
    if feature in ["MelSpectrogram", "MFCC"]:
        fig = px.imshow(features[feature], origin="lower", aspect="auto")
    elif feature.startswith("Pitch"):
        pitch, nccf = features["Pitch"][..., 0], features["Pitch"][..., 1]

        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        time_axis = torch.linspace(0, pitch.shape[-1], features["Waveform"].shape[-1])
        fig.add_trace(
            go.Scatter(
                x=time_axis,
                y=features["Waveform"],
                opacity=0.3,
                line={"color": "gray"},
                mode="lines",
                name="waveform",
            ),
            secondary_y=True,
        )

        time_axis = torch.arange(pitch.shape[-1])
        if feature.endswith("full"):
            fig.add_trace(
                go.Scatter(x=time_axis, y=nccf, mode="lines", name="nccf"),
                secondary_y=False,
            )
            fig.add_trace(
                go.Scatter(x=time_axis, y=pitch, mode="lines", name="pitch"),
                secondary_y=True,
            )
        else:
            p = nccf.clone()
            p[pitch < 0.2] = np.nan
            fig.add_trace(
                go.Scatter(x=time_axis, y=p, mode="lines", name="pitch"),
                secondary_y=False,
            )
    else:
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        time_axis = torch.arange(features[feature].shape[-1])
        fig.add_trace(
            go.Scatter(x=time_axis, y=features[feature], mode="lines", name=feature),
            secondary_y=False,
        )
        time_axis = torch.linspace(
            0, features[feature].shape[-1], features["Waveform"].shape[-1]
        )
        fig.add_trace(
            go.Scatter(
                x=time_axis,
                y=features["Waveform"],
                opacity=0.3,
                line={"color": "gray"},
                mode="lines",
                name="waveform",
            ),
            secondary_y=True,
        )
        # fig = px.line(features[feature])

    # Configure other layout properties
    fig.update_layout(
        height=500,
    )
    return fig


def get_trp_figure(tokens, trps):
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=trps,
            name="TRP",
        )
    )
    fig.update_yaxes(range=(0, 1))
    fig.update_layout(
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(len(tokens))),
            ticktext=tokens,
        )
    )
    fig.update_xaxes(tickangle=45)
    return fig


def get_dialog_text(all_turns, turn_index):
    turns = all_turns[: turn_index + 1]

    # utt = str(turns[0].start_time) + turns[0].utterance
    dialog = []
    if len(turns) > 0:
        utt = turns[0]["utterance"]
        last_name = turns[0]["name"]
        for t in turns[1:]:
            if t["utterance"] == "":
                continue
            if t["name"] == last_name:
                utt = utt + " " + clean_whitespace(t["utterance"])
            else:
                dialog.append(clean_whitespace(utt))
                # utt = str(t.start_time) + t['utterance']
                utt = clean_whitespace(t["utterance"])
                last_name = t["name"]
        dialog.append(clean_whitespace(utt))
    return dialog


def get_trps(dialog_text):
    URL_TRP = "http://localhost:5001/trp"
    json_data = {"text": dialog_text}
    response = requests.post(URL_TRP, json=json_data)
    d = json.loads(response.content.decode())
    return d


def get_turn_trp(turns, turn_index):
    dialog_text = get_dialog_text(turns, turn_index)
    trp = get_trps(dialog_text)
    sp = re.split(r"\<speaker\d\>", trp["tokens"])[-1].split()
    trps = trp["trp"][-len(sp) :]
    toks = trp["tokens"].split()[-len(sp) :]
    return toks, trps


parser = ArgumentParser()
parser.add_argument(
    "--root", type=str, default="/home/erik/.cache/agent/testing/travels/prediction"
)

args = parser.parse_args()

feature = "Pitch"
data = load_dialog_data(args.root)

# Audio
waveform = data["audio"]["waveform"]
waveform[1] = waveform[1] - waveform[1].min()
waveform[1] /= waveform[1].max()
waveform[1] -= waveform[1].mean()

sr = data["audio"]["sample_rate"]

# turns
turns = data["dialog"]["turns"]


n_turns = len(turns)
turn_index = 5
pre_pad = 0.5
post_pad = 0

turn, features = get_turn(turn_index, pre_pad, post_pad, turns, waveform, sr)
prev_utterance = turns[turn_index - 1]["utterance"]
tokens, trps = get_turn_trp(turns, turn_index)

wavpath = f"/tmp/audio_{turn_index}.wav"
torchaudio.save(filepath=wavpath, src=features["Waveform"].unsqueeze(0), sample_rate=sr)

################################################################################
# Layout
################################################################################

context = html.Div(
    children=[html.H1(children=f"Context"), html.Div(id="turn-utterance")],
    style={"textAlign": "center", "background": "white", "borderRadius": "3px"},
    id="turn-context",
)

turn_stats = html.Div(
    style={"background": "lightgray", "height": "100%"},
    children=[
        html.H3(children=f"Turn Statistics"),
        html.Div(id="turn-stats-nwords"),
        html.Div(id="turn-stats-duration"),
    ],
)

turn_ui = dbc.Row(
    style={"padding": "5px"},
    children=[
        dbc.Col(children=turn_stats, width=3),
        dbc.Col(
            children=[
                dcc.Dropdown(
                    options=[
                        {"label": "Waveform", "value": "Waveform"},
                        {"label": "MelSpectrogram", "value": "MelSpectrogram"},
                        {"label": "MFCC", "value": "MFCC"},
                        {"label": "Pitch", "value": "Pitch"},
                        {"label": "Pitch-full", "value": "Pitch-full"},
                        {"label": "Intensity", "value": "Intensity"},
                    ],
                    id="dropdown",
                    value=feature,
                ),
                dcc.Graph(
                    figure=get_figure(features, feature),
                    id="feature-graph",
                ),
                html.Div(
                    children=turn["utterance"],
                    style={"textAlign": "center", "background": "white"},
                    id="turn-text",
                ),
                dcc.Graph(
                    figure=get_trp_figure(tokens, trps),
                    id="trp-graph",
                ),
                html.Div(
                    style={"background": "white"},
                    children=html.Audio(
                        src=f"http://localhost:5002/api/audio{wavpath}",
                        controls=True,
                    ),
                    id="audio",
                ),
            ],
        ),
    ],
)

app.layout = html.Div(
    style={"textAlign": "center"},
    children=[
        html.H1(children=f"Turn: {turn_index}", id="turn-header"),
        html.Div(
            style={
                "textAlign": "center",
                "background": "darkgray",
                "padding": "3px",
                "borderRadius": "3px",
            },
            children=[context, turn_ui],
        ),
        dcc.Slider(
            min=0,
            max=n_turns,
            marks={i: f"{i}" if i == 1 else str(i) for i in range(n_turns)},
            id="turn-slider",
            value=turn_index,
        ),
    ],
)


@app.callback(
    Output(component_id="turn-header", component_property="children"),
    Output(component_id="turn-text", component_property="children"),
    Output(component_id="turn-utterance", component_property="children"),
    Output(component_id="turn-stats-nwords", component_property="children"),
    Output(component_id="turn-stats-duration", component_property="children"),
    Output(component_id="dropdown", component_property="value"),
    Output(component_id="trp-graph", component_property="figure"),
    Output(component_id="audio", component_property="children"),
    Input(component_id="turn-slider", component_property="value"),
)
def update_output_div(turn_index):
    global turn
    global features
    global wavpath

    turn, features = get_turn(turn_index, pre_pad, post_pad, turns, waveform, sr)
    prev_utterance = turns[turn_index - 1]["utterance"]
    tokens, trps = get_turn_trp(turns, turn_index)

    wavpath = f"/tmp/audio_{turn_index}.wav"
    torchaudio.save(
        filepath=wavpath, src=features["Waveform"].unsqueeze(0), sample_rate=sr
    )

    return [
        f"Turn: {turn_index}",
        turn["utterance"],
        prev_utterance,
        f"Words: {features['statistics']['n_words']}",
        f"Duration: {features['statistics']['duration']}",
        feature,
        get_trp_figure(tokens, trps),
        html.Audio(
            src=f"http://localhost:5002/api/audio{wavpath}",
            controls=True,
        ),
    ]


@app.callback(
    Output(component_id="feature-graph", component_property="figure"),
    Input(component_id="dropdown", component_property="value"),
)
def update_output_div(feature):
    return get_figure(features, feature)


if __name__ == "__main__":

    app.run_server(debug=True, use_reloader=True)  # Turn off reloader if inside Jupyter
