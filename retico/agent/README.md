# Agent or Spoken Dialog System



## VAD


The Vad module is a wrapper around google webrtc.Vad function. It operates of frames of 10, 20 or 30 ms. 

It simply transforms and AudioIUs into VadIUs. Where the only information we get is if the frame is
considered to include speech-activity or not.



This module may then be used in higher level VadModules that may smoothen the signal and estimate
EOT.


