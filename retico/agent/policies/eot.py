import json
import requests
import time

from retico.agent.utils import clean_whitespace, Color as C
from retico.agent.frontal_cortex import FrontalCortexBase

URL_TRP = "http://localhost:5001/trp"


class FC_EOT(FrontalCortexBase):
    def __init__(self, dm, trp_threshold=0.1, backchannel_prob=0.4, **kwargs):
        super().__init__(**kwargs)
        self.dm = dm
        self.trp_threshold = trp_threshold
        self.backchannel_prob = backchannel_prob

        self.turn_state_history = []

    @property
    def both_inactive(self):
        return not self.cns.user_asr_active and not self.cns.agent_speech_ongoing

    @property
    def both_active(self):
        return self.cns.user_asr_active and self.cns.agent_speech_ongoing

    @property
    def only_user_active(self):
        return self.cns.user_asr_active and not self.cns.agent_speech_ongoing

    @property
    def only_agent_active(self):
        return not self.cns.user_asr_active and self.cns.agent_speech_ongoing

    def lm_eot(self, text):
        json_data = {"text": text}
        response = requests.post(URL_TRP, json=json_data)
        d = json.loads(response.content.decode())
        return d["trp"][-1]  # only care about last token

    def respond_or_listen(self):
        current_utt = clean_whitespace(self.cns.user.utterance)
        if self.check_utterance_dialog_end(current_utt):
            self.dialog_ended = True
        else:
            context = self.cns.memory.get_dialog_text()
            context.append(current_utt)
            trp = self.lm_eot(context)

            if self.verbose:
                for i, utt in enumerate(context):
                    if i % 2 == 0:
                        print(C.blue + utt, C.end)
                    else:
                        print(C.yellow + utt, C.end)

            if trp >= self.trp_threshold:
                if self.verbose:
                    print(C.green + f"EOT recognized: {round(trp, 3)}" + C.end)
                self.cns.finalize_user()
                self.speak()
                self.cns.init_user_turn()
            else:
                if self.verbose:
                    print(C.red + f"listen: {1-round(trp, 3)}" + C.end)
                # if random.random() <= self.backchannel_prob:
                #     self.cns.backchannel("Go on.")

    def dialog_loop(self):
        """
        A constant loop which looks at the internal state of the agent, the estimated state of the user and the dialog
        state.

        """

        self.turn_state_history.append(self.BOTH_INACTIVE)

        if self.speak_first:
            self.cns.agent.planned_utterance, self.dialog_ended = self.dm.get_response()
            self.cns.start_speech(self.cns.agent.planned_utterance)

        while not self.dialog_ended:
            time.sleep(self.LOOP_TIME)

            last_state = self.turn_state_history[-1]

            if self.both_inactive:
                if self.verbose and last_state != self.BOTH_INACTIVE:
                    print(C.red + "BOTH INACTIVE" + C.end)

                if last_state == self.ONLY_USER:
                    end = self.respond_or_listen()
                    if end:
                        print("END EVERYTHING")
                        self.dialog_ended = True
                        break
                # elif last_state == self.ONLY_AGENT:
                #     self.cns.finalize_agent()
                else:
                    self.fallback_inactivity()
                self.turn_state_history.append(self.BOTH_INACTIVE)

            elif self.both_active:
                if self.verbose and last_state != self.BOTH_ACTIVE:
                    print(C.red + "DOUBLE TALK" + C.end)

                if last_state == self.ONLY_AGENT:
                    if self.is_interrupted():
                        self.should_reapeat()
                        self.cns.stop_speech(False)
                elif last_state == self.ONLY_USER:
                    finalize = True
                    if self.cns.agent.completion < 0.2:
                        finalize = False
                    self.cns.stop_speech(finalize)

                self.turn_state_history.append(self.BOTH_ACTIVE)

            elif self.only_user_active:
                self.fallback_inactivity()
                if self.verbose and last_state != self.ONLY_USER:
                    print(C.red + "USER" + C.end)
                self.turn_state_history.append(self.ONLY_USER)
            else:
                if self.verbose and last_state != self.ONLY_AGENT:
                    print(C.red + "AGENT" + C.end)
                self.turn_state_history.append(self.ONLY_AGENT)
        print("======== DIALOG DONE ========")
