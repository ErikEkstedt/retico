import requests
import json
import re
import time

from retico.core.abstract import (
    AbstractModule,
    AbstractConsumingModule,
)

from retico.core.text.common import SpeechRecognitionIU

from retico.agent.common import EotIU, SadIU
from retico.agent.utils import Color as C


URL_TRP = "http://localhost:5000/trp"


class EOT_ASR_DEBUG(AbstractConsumingModule):
    @staticmethod
    def input_ius():
        return [EotIU]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_eot_state = None
        self.last_text = ""

    def process_iu(self, input_iu):
        if input_iu.text != self.last_text:
            # if input_iu != self.last_eot_state:
            color = C.red
            if input_iu.eot:
                color = C.green
            s = color
            s += "EOT VAD DEBUG"
            s += f"\nEOT: {input_iu.eot} {round(input_iu.probability, 3)}"
            s += "\ntext: " + input_iu.text
            s += C.end
            print(s)
            self.last_eot_state = input_iu.eot
            self.last_text = input_iu.text


class EOT_ASR_FINAL(AbstractModule):
    @staticmethod
    def name():
        return "EOT-ASR-Final Module"

    @staticmethod
    def description():
        return "EOT based on ASR final"

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU]

    @staticmethod
    def output_iu():
        return EotIU

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.eot_state = True

    def process_iu(self, input_iu):
        if input_iu.final:
            self.eot_state = True
            output_iu = self.create_iu()
            output_iu.set_eot(eot=self.eot_state, text=input_iu.text)
            return output_iu
        else:
            if self.eot_state:
                self.eot_state = False
                output_iu = self.create_iu()
                output_iu.set_eot(eot=self.eot_state)
                return output_iu


class EOT_LM_Only(AbstractModule):
    @staticmethod
    def name():
        return "EOT-ASR-Final Module"

    @staticmethod
    def description():
        return "EOT based on ASR final"

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU]

    @staticmethod
    def output_iu():
        return EotIU

    def get_eot(self, text):
        json_data = {"text": text}
        response = requests.post(URL_TRP, json=json_data)
        d = json.loads(response.content.decode())
        return d["trp"][-1]  # only care about last token

    def __init__(self, trp_thresh=0.1, **kwargs):
        super().__init__(**kwargs)
        self.eot_state = None
        self.current_utterance = ""
        self.trp_thresh = trp_thresh

    def listen_other(self, input_iu):
        prel_utterance = (self.current_utterance + input_iu.text).strip()

        if input_iu.final:  # if final we append the utterance to store
            self.current_utterance = prel_utterance

        trp = self.get_eot(prel_utterance)
        if trp >= self.trp_thresh:  # trp found!
            self.current_utterance = ""
            self.eot_state = True
            output_iu = self.create_iu()
            output_iu.set_eot(probability=trp, eot=self.eot_state, text=prel_utterance)
            self.append(output_iu)
        else:
            if self.eot_state:
                self.eot_state = False
                output_iu = self.create_iu()
                output_iu.set_eot(
                    probability=trp, eot=self.eot_state, text=prel_utterance
                )
                self.append(output_iu)

    def process_iu(self, input_iu):
        if isinstance(input_iu, SpeechRecognitionIU):
            self.listen_other(input_iu)


class EOT_LM_Final(AbstractModule):
    @staticmethod
    def name():
        return "EOT-ASR-Final Module"

    @staticmethod
    def description():
        return "EOT based on ASR final"

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU]

    @staticmethod
    def output_iu():
        return EotIU

    def get_eot(self, text):
        json_data = {"text": text}
        response = requests.post(URL_TRP, json=json_data)
        d = json.loads(response.content.decode())
        return d["trp"][-1]  # only care about last token

    def __init__(self, trp_thresh=0.1, **kwargs):
        super().__init__(**kwargs)
        self.eot_state = None
        self.current_utterance = ""
        self.trp_thresh = trp_thresh

    def listen_other(self, input_iu):
        if input_iu.final:  # if final we append the utterance to store
            self.current_utterance += " " + input_iu.text
            self.current_utterance = re.sub("\s\s+", " ", self.current_utterance)

            trp = self.get_eot(self.current_utterance)
            if trp >= self.trp_thresh:  # trp found!
                self.eot_state = True
                output_iu = self.create_iu()
                output_iu.set_eot(
                    probability=trp, eot=self.eot_state, text=self.current_utterance
                )
                self.current_utterance = ""
                self.append(output_iu)
            else:
                if self.eot_state:
                    self.eot_state = False
                    output_iu = self.create_iu()
                    output_iu.set_eot(
                        probability=trp, eot=self.eot_state, text=self.current_utterance
                    )
                    self.append(output_iu)

    def process_iu(self, input_iu):
        if isinstance(input_iu, SpeechRecognitionIU):
            self.listen_other(input_iu)


class EOT_LM_Sad(AbstractModule):
    @staticmethod
    def name():
        return "EOT-ASR-Final Module"

    @staticmethod
    def description():
        return "EOT based on ASR final"

    @staticmethod
    def input_ius():
        return [SpeechRecognitionIU, SadIU]

    @staticmethod
    def output_iu():
        return EotIU

    def get_eot(self, text):
        json_data = {"text": text}
        response = requests.post(URL_TRP, json=json_data)
        d = json.loads(response.content.decode())
        return d["trp"][-1]  # only care about last token

    def __init__(self, trp_thresh=0.1, **kwargs):
        super().__init__(**kwargs)
        self.trp_thresh = trp_thresh

        self.current_utterance = ""
        self.preliminary_utterance = ""
        self.last_sent_eot_state = None
        self.latest_trp = 0
        self.user_is_speaking = False

    def update(self):
        output_iu = None
        if self.last_sent_eot_state is None:
            output_iu = self.create_iu()
            output_iu.set_eot(
                probability=self.latest_trp,
                eot=False,
                text="SSTART",
            )
            self.last_sent_eot_state = False
            # self.append(output_iu)
            # return

        elif not self.user_is_speaking and self.latest_trp > self.trp_thresh:
            output_iu = self.create_iu()
            output_iu.set_eot(
                probability=self.latest_trp, eot=True, text=self.preliminary_utterance
            )
            self.last_sent_eot_state = True
            self.current_utterance = ""
            self.preliminary_utterance = ""
            # self.append(output_iu)
            # time.sleep(0.05)
            # return

        elif self.last_sent_eot_state is None or self.last_sent_eot_state != False:
            output_iu = self.create_iu()
            output_iu.set_eot(
                probability=self.latest_trp,
                eot=False,
                text=self.preliminary_utterance,
            )
            self.last_sent_eot_state = False
            # self.append(output_iu)
        return output_iu

    def handle_sad(self, input_iu):
        """simply updates the user state"""
        self.user_is_speaking = input_iu.is_speaking
        return self.update()

    def listen_other(self, input_iu):
        self.preliminary_utterance = self.current_utterance + " " + input_iu.text
        self.preliminary_utterance = re.sub(
            "\s\s+", " ", self.preliminary_utterance
        ).strip()

        if input_iu.final:  # if final we append the utterance to store
            self.current_utterance = self.preliminary_utterance

        self.latest_trp = self.get_eot(self.preliminary_utterance)
        # print("prel: ", self.preliminary_utterance)
        # print("trp: ", self.latest_trp)
        # print()
        return self.update()

    def process_iu(self, input_iu):
        if isinstance(input_iu, SpeechRecognitionIU):
            return self.listen_other(input_iu)
        elif isinstance(input_iu, SadIU):
            return self.handle_sad(input_iu)


def test_eot_asr():
    from retico.agent.hearing import Hearing

    sample_rate = 16000
    chunk_time = 0.01
    bytes_per_sample = 2

    hearing = Hearing(
        chunk_time=chunk_time,
        sample_rate=sample_rate,
        bytes_per_sample=bytes_per_sample,
        use_asr=True,
        record=False,
        debug=False,
    )
    eot_asr_final = EOT_ASR_FINAL()
    eot_asr_final_debug = EOT_ASR_DEBUG()

    # Connect Components
    hearing.asr.subscribe(eot_asr_final)
    eot_asr_final.subscribe(eot_asr_final_debug)

    # run
    hearing.run_components()
    eot_asr_final.run()
    eot_asr_final_debug.run()
    try:
        input()
    except KeyboardInterrupt:
        pass
    hearing.stop_components()
    eot_asr_final.stop()
    eot_asr_final_debug.stop()


def test_eot_lm_only():
    from retico.agent.hearing import Hearing

    sample_rate = 16000
    chunk_time = 0.01
    bytes_per_sample = 2

    hearing = Hearing(
        chunk_time=chunk_time,
        sample_rate=sample_rate,
        bytes_per_sample=bytes_per_sample,
        use_asr=True,
        record=False,
        debug=False,
    )
    eot_lm_only = EOT_LM_Only()
    eot_asr_final_debug = EOT_ASR_DEBUG()

    # Connect Components
    hearing.asr.subscribe(eot_lm_only)
    eot_lm_only.subscribe(eot_asr_final_debug)

    # run
    hearing.run_components()
    eot_lm_only.run()
    eot_asr_final_debug.run()
    try:
        input()
    except KeyboardInterrupt:
        pass
    hearing.stop_components()
    eot_lm_only.stop()
    eot_asr_final_debug.stop()


def test_eot_lm_final():
    from retico.agent.hearing import Hearing

    sample_rate = 16000
    chunk_time = 0.01
    bytes_per_sample = 2

    hearing = Hearing(
        chunk_time=chunk_time,
        sample_rate=sample_rate,
        bytes_per_sample=bytes_per_sample,
        use_asr=True,
        record=False,
        debug=False,
    )
    eot_lm_final = EOT_LM_Final()
    eot_asr_final_debug = EOT_ASR_DEBUG()

    # Connect Components
    hearing.asr.subscribe(eot_lm_final)
    eot_lm_final.subscribe(eot_asr_final_debug)

    # run
    hearing.run_components()
    eot_lm_final.run()
    eot_asr_final_debug.run()
    try:
        input()
    except KeyboardInterrupt:
        pass
    hearing.stop_components()
    eot_lm_final.stop()
    eot_asr_final_debug.stop()


def test_eot_lm_sad():
    from retico.agent.hearing import Hearing
    from retico.agent.sad import SADModule

    sample_rate = 16000
    chunk_time = 0.01
    bytes_per_sample = 2

    hearing = Hearing(
        chunk_time=chunk_time,
        sample_rate=sample_rate,
        bytes_per_sample=bytes_per_sample,
        use_asr=True,
        record=False,
        debug=False,
    )
    sad = SADModule(chunk_time=chunk_time, vad_off_time=0.5, vad_on_time=0.1)
    eot_lm_sad = EOT_LM_Sad()
    eot_asr_final_debug = EOT_ASR_DEBUG()

    # Connect Components
    hearing.asr.subscribe(eot_lm_sad)
    hearing.vad.subscribe(sad)
    sad.subscribe(eot_lm_sad)
    eot_lm_sad.subscribe(eot_asr_final_debug)

    # run
    hearing.run_components()
    sad.run()
    eot_lm_sad.run()
    eot_asr_final_debug.run()
    try:
        input()
    except KeyboardInterrupt:
        pass
    hearing.stop_components()
    eot_lm_sad.stop()
    sad.stop()
    eot_asr_final_debug.stop()


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("--module", type=str)
    args = parser.parse_args()

    if args.module == "asr":
        print("ASR-final")
        print()
        test_eot_asr()
    elif args.module == "lm_only":
        print("LM ONLY")
        print()
        test_eot_lm_only()
    elif args.module == "lm_final":
        print("LM + ASR-Final")
        print()
        test_eot_lm_final()
    elif args.module == "lm_sad":
        print("LM + SAD")
        print()
        test_eot_lm_sad()
    else:
        raise NotImplementedError()
