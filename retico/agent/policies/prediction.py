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
        self.t_predicted_user_off = 0

    def lm_prediction(self, text):
        json_data = {"text": text}
        response = requests.post(URL_Prediction, json=json_data)
        d = json.loads(response.content.decode())
        return d

    def predict_trp(self, current_utt):
        self.last_current_utterance = current_utt
        context = self.cns.memory.get_dialog_text()
        context.append(current_utt)

        res = self.lm_prediction(context)
        trp = res["p"]
        return trp

    def trigger_user_turn_off(self):
        should_respond = False
        if self.cns.user_turn_active:
            if not self.cns.vad_ipu_active:
                current_utt = clean_whitespace(self.cns.user.prel_utterance)
                if current_utt != "" and current_utt != self.last_current_utterance:
                    print("guessing")
                    self.last_current_utterance = current_utt
                    trp = self.predict_trp(current_utt)
                    self.cns.user.all_trps.append({"trp": trp, "time": time.time()})
                    self.last_guess = "trp"
                    if trp >= self.trp_threshold:
                        should_respond = True
                        self.cns.user.trp_at_eot = trp
                        self.cns.user.utterance_at_eot = current_utt
                        self.t_predicted_user_off = time.time()
                        self.cns.finalize_user()
                        if self.verbose:
                            print(C.green + f"EOT recognized: {round(trp, 3)}" + C.end)
                    else:
                        if self.verbose:
                            if self.last_guess != "listen":
                                print(C.red + f"listen: {1-round(trp, 3)}" + C.end)
                        self.last_guess = "listen"
        return should_respond

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
            if self.trigger_user_turn_off():
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
