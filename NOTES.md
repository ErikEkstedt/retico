# Notes

A place to keep some notes on the Retico framework while learning/working on the framw work.

General Questions
* Right buffer
* Left buffer


------------------------

# Incremental Units
> An abstract incremental unit.
> The IU may be used for ASR, NLU, DM, TT, TTS, ... It can be redefined to fit the needs of the different module (and module-types) but should always provide these functionalities.
>
> The meta_data may be used when an incremental module is having additional information because it is working in a simulated environemnt. This data can be used by later modules to keep the simulation going.

```python
"""
  Attributes:
      creator (AbstractModule): The module that created this IU
      previous_iu (IncrementalUnit): A link to the IU created before the
          current one.
      grounded_in (IncrementalUnit): A link to the IU this IU is based on.
      created_at (float): The UNIX timestamp of the moment the IU is created.
      meta_data (dict): Meta data that offers optional meta information. This
          field can be used to add information that is not available for all
          uses of the specific incremental unit.
"
```

Questions: 
* What's the difference between the `previous_iu` and the `grounded_in` unit?
  * Could the previous perhaps be the latest IU but the current IU might be grounded in anothor IU from another modality?


------------------------

# IO

## MicrophoneModule
> A module that produces IUs containing audio signals that are captures by a microphone.


## SpeakerModule
> A module that consumes AudioIUs of arbitrary size and outputs them to the speakers of the machine. When a new IU is incoming, the module blocks as long as the current IU is being played. 


## StreamingSpeakerModule
> A module that consumes Audio IUs and outputs them to the speaker of the machine. The audio output is streamed and thus the Audio IUs have to have exactly [chunk_size] samples.


## AudioDispatcherModule
> An Audio module that takes a raw audio stream of arbitrary size and outputs AudioIUs with a specific chunk size at the rate it would be produced if the audio was being played.  This could be espacially useful when an agents' TTS module produces an utterance, but this utterance should not be transmitted as a whole but in an incremental way.

------------------------

# ASR

## GoogleASRModule

Does what the name implies. Returns SpeechRecognitionIUs with `iu.text`, `iu.stability`, `iu.final`.


## IncrementalizeASRModule

Handles the output from an asr module but only outputs the newly added words not already heard.


------------------------
# Dialog

## [TurnTakingDialogueManagerModule](https://github.com/Uhlo/retico/blob/master/retico/modules/simulation/dm.py)

The focus of my efforts?
