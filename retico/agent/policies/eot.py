import json
import requests
import time

from retico.agent.utils import clean_whitespace, Color as C
from retico.agent.frontal_cortex import FrontalCortexBase

URL_TRP = "http://localhost:5001/trp"


class FC_EOT(FrontalCortexBase):
    def __init__(self, trp_threshold=0.1, **kwargs):
        super().__init__(**kwargs)
        self.trp_threshold = trp_threshold

        self.last_guess = None
        self.last_current_utterance = None

    def lm_eot(self, text):
        json_data = {"text": text}
        response = requests.post(URL_TRP, json=json_data)
        d = json.loads(response.content.decode())
        return d["trp"][-1]  # only care about last token

    def trigger_user_turn_off(self):
        should_respond = False
        if self.cns.user_turn_active:
            if not self.cns.vad_ipu_active and not self.cns.asr_active:
                current_utt = clean_whitespace(self.cns.user.utterance)
                if current_utt != self.last_current_utterance:
                    self.last_current_utterance = current_utt
                    context = self.cns.memory.get_dialog_text()
                    context.append(current_utt)
                    trp = self.lm_eot(context)
                    self.cns.user.all_trps.append({"trp": trp, "time": time.time()})
                    self.last_guess = "trp"
                    if trp >= self.trp_threshold:
                        should_respond = True
                        self.cns.user.trp_at_eot = trp
                        self.cns.user.utterance_at_eot = current_utt
                        self.cns.finalize_user()
                        if self.verbose:
                            print(C.green + f"EOT recognized: {round(trp, 3)}" + C.end)
                    else:
                        if self.verbose:
                            if self.last_guess != "listen":
                                print(C.red + f"listen: {1-round(trp, 3)}" + C.end)
                        self.last_guess = "listen"
        return should_respond
