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

* []




-----------------------------

## Components

###  VAD

The Vad module is a wrapper around google webrtc.Vad function. It operates of frames of 10, 20 or 30 ms. 

It simply transforms and AudioIUs into VadIUs. Where the only information we get is if the frame is
considered to include speech-activity or not.

This module may then be used in higher level VadModules that may smoothen the signal and estimate
EOT.
