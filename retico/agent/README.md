# Agent or Spoken Dialog System


## Agent


### CentralNervousSystem, CNS

Connects the input perception (incomming text/audio, self-hearing) and provides the action methods (start_speech, stop_speech, finalize_user). 


### FrontalCortex, FC

The frontal cortex is where all the decision making and higher level processing is done. This class have access to the CNS and uses this to deterimne the dialog state of the conversation.  This module should determine the turn-state of the dialog by calling either `finalize_user` or `finalize_agent` which finalizes the turn and adds it into memory.

Given the state of the dialog the frontal cortex determines the next action, by default a "non-action" is the same as listening, that is to simply do nothing.

#### Loop

The loop determines the clock rate of the central decision making process. Each step pauses for `SLEEP_TIME` seconds (e.g. .05 = 50ms) and then checks in on the CNS to determine what the current state is. At each point we want to know the current state and the transition for being here or simply the last and current state.

* ONLY_Agent -> BOTH_INACTIVE -> listen, fallback
* ONLY_USER -> BOTH_INACTIVE -> speak, fallback
* ONLY_Agent -> BOTH_ACTIVE -> is-interrupted? stop_speech, do nothing.
* BOTH_INACTIVE -> ONLY_USER -> listen
* ONLY_USER -> BOTH_ACTIVE -> Should not reach this state unless overlap action are used.


#### TODO

* [ ] Record all audio in a coherent way



-----------------------------

## Components

###  VAD

The Vad module is a wrapper around google webrtc.Vad function. It operates of frames of 10, 20 or 30 ms. 

It simply transforms and AudioIUs into VadIUs. Where the only information we get is if the frame is
considered to include speech-activity or not.

This module may then be used in higher level VadModules that may smoothen the signal and estimate
EOT.

-----------------------------

## Bypass

Bypass the audio around the system in order to use the agent over zooom.


- Use Jack
- Open `catia`
  - patchbay for Jack
  - visual interface for our audio modules
- Add a new sink/source pair using `pactl`

```bash
pactl load-module module-jack-sink client_name=pulse_sink_2 channels=2 connect=no
pactl load-module module-jack-source client_name=pulse_source_2 channels=2 connect=no
```

- Add special connections for headset to listen in on answers
```bash
alsa_out -j HeadsetOut -d hw:CARD=S7 -r 44100 channels=2 >/dev/null &
```

- then start zoom/voice app
    - choose the created sink/source for microphone and speaker
- Hearing is working.   
  - run `python hearing.py --bypass --debug`
  - Use the zoom-speaker-device as input device
  - using the `bypass` device instead of the system microphone...
- Speech is NOT working.   
  - run `python speech.py --bypass --debug`
  - Use the zoom-microphone-device as output module in `Speech`
  - [ ] Fix resample in TTS-module
      - always use 16000khz for the tts api
      - resample the audio before sending it to the output device
  - Sample rate from tts is `8/16/22/24 kHz` and jack operates on 44100/48000 and others by default but not 16000
- Agent
  - The agent is not working because it interrupts itself.
  - The audio from the system goes to speakers and back into the system
