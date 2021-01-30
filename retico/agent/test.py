from retico.agent import Hearing, Speech
from retico.agent.CNS import CNS
from retico.agent.agent import SimpleFC, FC_Baseline, FC_EOT
from retico.agent.agent_prediction import FC_Predict, CNS_Continuous
from retico.agent.dm import DM
from retico.agent.vad import VADModule


def test_cns(args):
    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        use_asr=True,
        record=False,
        debug=False,
    )
    speech = Speech(
        chunk_time=args.speech_chunk_time,
        sample_rate=args.speech_sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        tts_client="amazon",
        output_word_times=True,
        debug=False,
    )
    cns = CNS(verbose=args.verbose)
    frontal = SimpleFC(
        central_nervous_system=cns,
        fallback_duration=args.fallback_duration,
        verbose=args.verbose,
    )

    hearing.asr.subscribe(cns)
    speech.audio_dispatcher.subscribe(cns)
    speech.tts.subscribe(cns)
    cns.subscribe(speech.tts)

    hearing.run_components()
    speech.run()
    cns.run()  # starts the loop

    frontal.start_loop()
    input()

    hearing.stop_components()
    speech.tts.shutdown()
    speech.stop()
    cns.stop()


def test_fc_baseline(args):
    from retico.agent import Hearing, Speech
    from retico.agent.vad import VADModule

    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        use_asr=True,
        record=False,
        debug=False,
    )
    speech = Speech(
        chunk_time=args.speech_chunk_time,
        sample_rate=args.speech_sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        tts_client="amazon",
        output_word_times=True,
        debug=False,
    )
    cns = CNS(verbose=args.verbose)
    dm = DM()
    vad = VADModule(
        chunk_time=args.chunk_time,
        onset_time=0.2,
        turn_offset=0.75,
        ipu_offset=0.3,
        fast_offset=0.1,
        prob_thresh=0.9,
    )
    frontal = FC_Baseline(
        dm=dm,
        central_nervous_system=cns,
        fallback_duration=args.fallback_duration,
        verbose=args.verbose,
    )

    hearing.asr.subscribe(cns)
    hearing.vad_frames.subscribe(vad)
    speech.audio_dispatcher.subscribe(cns)
    speech.tts.subscribe(cns)
    cns.subscribe(speech.tts)

    vad.event_subscribe(vad.EVENT_VAD_TURN_CHANGE, cns.vad_callback)
    vad.event_subscribe(vad.EVENT_VAD_IPU_CHANGE, cns.vad_callback)
    vad.event_subscribe(vad.EVENT_VAD_FAST_CHANGE, cns.vad_callback)

    hearing.run_components()
    speech.run()
    vad.run()
    cns.run()  # starts the loop

    frontal.start_loop()

    input()

    cns.memory.save("dialog_baseline.json")
    hearing.stop_components()
    speech.tts.shutdown()
    speech.stop()
    vad.stop()
    cns.stop()


def test_fc_eot(args):
    from retico.agent import Hearing, Speech
    from retico.agent.dm import DM

    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        use_asr=True,
        record=False,
        debug=False,
    )
    speech = Speech(
        chunk_time=args.speech_chunk_time,
        sample_rate=args.speech_sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        tts_client="amazon",
        output_word_times=True,
        debug=False,
    )
    cns = CNS(verbose=args.verbose)
    dm = DM()
    frontal = FC_EOT(
        dm=dm,
        central_nervous_system=cns,
        trp_threshold=args.trp,
        fallback_duration=args.fallback_duration,
        backchannel_prob=args.backchannel_prob,
        verbose=args.verbose,
    )

    hearing.asr.subscribe(cns)
    speech.audio_dispatcher.subscribe(cns)
    speech.tts.subscribe(cns)
    cns.subscribe(speech.tts)

    hearing.run_components()
    speech.run()
    cns.run()  # starts the loop

    frontal.start_loop()

    input("DIALOG\n")
    cns.memory.save("dialog_eot.json")

    hearing.stop_components()
    speech.tts.shutdown()
    speech.stop()
    cns.stop()


def test_prediction(args):
    hearing = Hearing(
        chunk_time=args.chunk_time,
        sample_rate=args.sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        use_asr=True,
        record=False,
        debug=False,
    )
    speech = Speech(
        chunk_time=args.speech_chunk_time,
        sample_rate=args.speech_sample_rate,
        bytes_per_sample=args.bytes_per_sample,
        tts_client="amazon",
        output_word_times=True,
        debug=False,
    )
    cns = CNS_Continuous(verbose=args.verbose)
    dm = DM()
    vad = VADModule(
        chunk_time=args.chunk_time,
        onset_time=0.2,
        turn_offset=0.75,
        ipu_offset=0.3,
        fast_offset=0.1,
        prob_thresh=0.9,
    )
    frontal = FC_Predict(
        dm=dm,
        central_nervous_system=cns,
        trp_threshold=args.trp,
        fallback_duration=args.fallback_duration,
        verbose=args.verbose,
    )

    hearing.asr.subscribe(cns)
    hearing.vad_frames.subscribe(vad)
    speech.audio_dispatcher.subscribe(cns)
    speech.tts.subscribe(cns)
    cns.subscribe(speech.tts)

    vad.event_subscribe(vad.EVENT_VAD_TURN_CHANGE, cns.vad_callback)
    vad.event_subscribe(vad.EVENT_VAD_IPU_CHANGE, cns.vad_callback)
    vad.event_subscribe(vad.EVENT_VAD_FAST_CHANGE, cns.vad_callback)

    hearing.run_components()
    speech.run()
    cns.run()  # starts the loop
    vad.run()

    frontal.start_loop()

    input("DIALOG\n")
    cns.memory.save("dialog_prediction.json")

    hearing.stop_components()
    speech.tts.shutdown()
    speech.stop()
    vad.stop()
    cns.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DialogState")
    parser.add_argument("--chunk_time", type=float, default=0.01)
    parser.add_argument("--sample_rate", type=int, default=16000)
    parser.add_argument("--speech_chunk_time", type=float, default=0.1)
    parser.add_argument("--speech_sample_rate", type=int, default=16000)
    parser.add_argument("--bytes_per_sample", type=int, default=2)
    parser.add_argument("--trp", type=float, default=0.1)
    parser.add_argument("--fallback_duration", type=float, default=3)
    parser.add_argument("--backchannel_prob", type=float, default=0.4)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--test", type=str, default="cns")
    args = parser.parse_args()

    if args.test == "cns":
        test_cns(args)
    elif args.test == "baseline":
        test_fc_baseline(args)
    elif args.test == "eot":
        test_fc_eot(args)
    elif args.test == "prediction":
        test_prediction(args)
    else:
        print(f"{args.test} not implemented. Try: [cns, asr]")
