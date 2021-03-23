import requests
import json
import time

from retico.agent.frontal_cortex import FrontalCortexBase
from retico.agent.utils import clean_whitespace, Color as C

URL_Prediction = "http://localhost:5001/prediction"

"""

Deactivate user but reactivate if erroneous
-------------------------------------------

User speaks
trigger_user_turn_off: should take turn

if is_interrupted inside of N-seconds -> reactivate user
- self.cns.user = self.cns.memory.user_turns.pop(-1)

Wait before deactivating user
-------------------------------------------
trigger_user_turn_off: should take turn but NOT finalize user

Inside

"""


class FC_Predict(FrontalCortexBase):
    def __init__(self, trp_threshold=0.1, **kwargs):
        super().__init__(**kwargs)
        self.trp_threshold = trp_threshold

        self.last_current_utterance = ""
        # self.t_predicted_user_off = 0

    def lm_prediction(self, text):
        json_data = {"text": text}
        response = requests.post(URL_Prediction, json=json_data)
        d = json.loads(response.content.decode())
        return d

    def predict_trp(self, current_utt):
        context, last_speaker = self.cns.memory.get_dialog_text()
        context.append(current_utt)
        return self.lm_prediction(context)

    def trigger_user_turn_off(self):
        should_respond = False
        if self.cns.user_turn_active and not self.cns.vad_ipu_active:
            current_utt = clean_whitespace(self.cns.user.prel_utterance)
            if current_utt != "" and current_utt != self.last_current_utterance:
                # print("guessing")

                # update last prediction text
                self.last_current_utterance = current_utt

                # get result from prediction model
                result = self.predict_trp(current_utt)
                trp = result["p"]

                # append trp estimate, the current time and duration of prediction
                print("pred time: ", result["time"])
                self.cns.user.all_trps.append(
                    {
                        "trp": trp,
                        "utterance": current_utt,
                        "predictions": result["predictions"],
                        "prediction_time": result["time"],
                        "time": time.time(),
                    }
                )
                self.cns.user.pred_time.append(result["time"])
                # self.last_guess = "trp"

                # check if a turn-shift is recognized
                if trp >= self.trp_threshold:
                    print("pos trp")
                    self.cns.user.trp_at_eot = trp
                    self.cns.user.utterance_at_eot = current_utt
                    # self.t_predicted_user_off = time.time()
                    # print("last_agent_trigger_on: ", self.last_agent_trigger_on)
                    # print("should respond: TRUE")
                    should_respond = True
                    # self.cns.finalize_user()
                    if self.verbose:
                        print(C.green + f"Take turn: {round(trp, 3)}" + C.end)
                else:
                    print("neg trp")
                    if self.verbose:
                        print(C.green + f"Listen: ", C.red, f"{round(trp, 3)}" + C.end)
                    # self.last_guess = "listen"

        return should_respond
