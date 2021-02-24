# Agent

## Run

```bash
# Don't forget the external LM server :)
python agent.py --dm_type experiment --root /PATH/TO/SAVE_DIR --task travel --policy baseline --trp .2 --bypass
```

### CentralNervousSystem, CNS

Connects the input perception (incomming text/audio, self-hearing) and provides the action methods (start\_speech, stop\_speech, finalize\_user, finalize\_agent). 


### FrontalCortex, FC

The frontal cortex is where all the decision making and higher level processing is done. This class have access to the CNS and uses this to deterimne the dialog state of the conversation.  This module should determine the turn-state of the dialog by calling either `finalize_user` or `finalize_agent` which finalizes the turn and adds it into memory.

Given the state of the dialog the frontal cortex determines the next action, by default a "non-action" is the same as listening, that is to simply do nothing.

#### Loop

The loop determines the clock rate of the central decision making process. Each step pauses for `SLEEP_TIME` seconds (e.g. 0.05=50ms)

```python
  def dialog_loop(self):
      """
      A constant loop which looks at the internal state of the agent, the estimated state of the user and the dialog
      state.

      """
      if self.speak_first:
          planned_utterance, self.dialog_ended = self.dm.get_response()
          self.cns.init_agent_turn(planned_utterance)

      while not self.dialog_ended:
          time.sleep(self.LOOP_TIME)

          self.trigger_user_turn_on()
          if self.trigger_user_turn_off():  # policy specific
              self.get_response_and_speak()

          self.fallback_inactivity()

          # updates the state if necessary
          current_state = self.update_dialog_state()
          if current_state == self.BOTH_ACTIVE:
              if self.is_interrupted():
                  self.should_repeat()
                  self.cns.stop_speech(finalize=True)
                  self.retrigger_user_turn()  # put after stop speech
      print("======== DIALOG LOOP DONE ========")
```



-----------------------------

## Components

* Hearing
  * VAD
  * ASR
* Speech
  * TTS
  * AudioDispatcher
* DM
  * simple questionare using an external LM for ranking
* CentralNervousSystem, CNS
  * The incremental dialog nexus
* Frontal Cortex, FC
  * the dialog loop/behavior
  * superclass extended by different policies

  
## Bypass

**Only tested on Linux**

Bypass the audio around the system in order to use the agent over zooom. Run the commands below to add new audio-modules and user their device names in the agents Zoom.

```bash
pactl load-module module-jack-sink client_name=zoom_sink channels=2 connect=no
pactl load-module module-jack-source client_name=zoom_source channels=2 connect=no
```

Make sure to add the `--bypass` flag in order to use the correct audio modules (hardcoded to the modules above).

```bash
python agent.py --dm_type experiment --root /PATH/TO/SAVE_DIR --task travel --policy baseline --trp .2 --bypass
```


### Misc on linux

**Check the audio routing**
- Use [Jack](https://jackaudio.org/)
- Open [Catia](https://kx.studio/Applications:Catia)
  - a patchbay for Jack
  - visual interface for our audio modules
  - used to check if zoom is connected correctly
- Add a new sink/source pair using `pactl`
- Add special connections for headset to listen in on answers
```bash
alsa_out -j HeadsetOut -d hw:CARD=S7 -r 44100 channels=2 >/dev/null &
```
- start zoom/voice app
    - choose the created sink/source for microphone and speaker
