import requests
import json
import time

from retico.agent.CNS import CentralNervousSystem
from retico.agent.frontal_cortex import FrontalCortexBase
from retico.agent.utils import clean_whitespace, Color as C

URL_Prediction = "http://localhost:5001/prediction"


class CNS_Continuous(CentralNervousSystem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user_turn_end_predicted = False

    def set_user_turn_on(self):
        if not self.user_turn_active:
            print(C.green + "########## ON user state ########" + C.end)
            self.user.start_time = time.time()
            self.user_turn_active = True

    def set_user_turn_off(self):
        if self.user_turn_active:
            print(C.red + "########## OFF user state ########" + C.end)
            self.user_turn_end_predicted = False
            self.finalize_user()

    def asr(self, input_iu):
        """Process the ASR input

        This is a passive ASR which does not trigger any turn-taking behaviour.

        * Activates `self.user_asr_active` and start recording text in a new turn
        * If `self.user_asr_active` is activated we call `self.set_user_turn_on`
        * If ASR FINAL:
            - The asr will collect new text and dismiss the previous

        """

        # Activate user-asr state
        if not self.user_asr_active:
            # self.set_user_turn_on()
            self.user_asr_active = True
            self.user.asr_start_time = time.time()
            if self.verbose:
                print(C.cyan + f"ASR Onset: {self.user_asr_active}" + C.end)

        # Update the utterance hypothesis
        self.user.prel_utterance = self.user.utterance + input_iu.text

        if input_iu.final:
            self.user_asr_active = False  # asr non active
            now = time.time()
            self.user.asr_end_time = now
            self.user_last_asr_end_time = now

            # update the utterance
            self.user.utterance = self.user.prel_utterance

            # if we have predicted the end of the turn we finalize user
            # The ASR could still process the incomming text after the TS is predicted
            if self.user_turn_end_predicted:
                self.set_user_turn_off()  # finalize user

            # if self.
            if self.verbose:
                print(C.cyan + "ASR Final updated last" + C.end)


class FC_Predict(FrontalCortexBase):
    def __init__(self, dm, trp_threshold=0.1, **kwargs):
        super().__init__(**kwargs)
        self.dm = dm
        self.trp_threshold = trp_threshold

        self.last_context = ""
        self.last_current_utterance = ""
        # self.last_user_asr_active = False

        self.turn_state_history = []

    @property
    def both_inactive(self):
        return not self.cns.user_turn_active and not self.cns.agent_speech_ongoing

    @property
    def both_active(self):
        return self.cns.user_turn_active and self.cns.agent_speech_ongoing

    @property
    def only_user_active(self):
        return self.cns.user_turn_active and not self.cns.agent_speech_ongoing

    @property
    def only_agent_active(self):
        return not self.cns.user_turn_active and self.cns.agent_speech_ongoing

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

    def respond_or_listen(self):
        current_utt = clean_whitespace(self.cns.user.prel_utterance)
        if self.check_utterance_dialog_end(current_utt):
            self.dialog_ended = True
        elif current_utt != "" and current_utt != self.last_current_utterance:
            trp = self.predict_trp(current_utt)
            if self.verbose:
                print("-" * 50)
                print(C.cyan + "Fast REACTION" + C.end)
                context_debug = self.cns.memory.get_dialog_text_debug()
                for i, utt in enumerate(context_debug[:-1]):
                    if i % 2 == 0:
                        print(C.blue + utt, C.end)
                    else:
                        print(C.yellow + utt, C.end)

            # If we predict a turn-shift we query the DM and initiate speech
            if trp >= self.trp_threshold:
                self.cns.user.utterance_at_eot = current_utt
                self.cns.user.trp_at_eot = trp
                self.cns.user_turn_end_predicted = True
                if self.verbose:
                    print(C.yellow + current_utt + C.green + f" -> ## {trp} ##" + C.end)
                    print(
                        C.yellow
                        + str(self.cns.user.start_time)
                        + current_utt
                        + C.green
                        + f" -> ## {trp} ##"
                        + C.end
                    )
                    print("-" * 50)
                self.speak()
                self.user_turn_off()
            else:
                if self.verbose:
                    print(C.yellow + current_utt + C.red + f" -> ## {trp} ##" + C.end)
                    print(
                        C.yellow
                        + str(self.cns.user.start_time)
                        + current_utt
                        + C.red
                        + f" -> ## {trp} ##"
                        + C.end
                    )
                    print("-" * 50)
                self.cns.user_turn_end_predicted = False

    def trigger_user_turn_on(self):
        """The user turn has started.
        1. a) User turn is OFF
        1. b) The ASR module is OFF -> last_user_asr_active = False
        2. ASR turns on -> now we decode text -> last_user_asr_active = True
        """
        if not self.cns.user_turn_active:
            if self.cns.vad_ipu_active:
                print("VAD activation")
                self.cns.init_user_turn()
                self.cns.set_user_turn_on()
                # self.last_user_asr_active = True

    def user_turn_off(self):
        print(C.red + "########## OFF (FC) user state ########" + C.end)
        self.cns.set_user_turn_off()
        # self.last_user_asr_active = False

    def update_state(self):
        if self.only_user_active:
            if self.verbose and self.turn_state_history[-1] != self.ONLY_USER:
                print(C.red + "USER" + C.end)
            self.turn_state_history.append(self.ONLY_USER)
        elif self.both_inactive:
            if self.verbose and self.turn_state_history[-1] != self.BOTH_INACTIVE:
                print(C.red + "BOTH INACTIVE" + C.end)
            self.turn_state_history.append(self.BOTH_INACTIVE)
        elif self.both_active:
            if self.verbose and self.turn_state_history[-1] != self.BOTH_ACTIVE:
                print(C.red + "DOUBLE TALK" + C.end)
            self.turn_state_history.append(self.BOTH_ACTIVE)
        else:
            if self.verbose and self.turn_state_history[-1] != self.ONLY_AGENT:
                print(C.red + "AGENT" + C.end)
            self.turn_state_history.append(self.ONLY_AGENT)

    def dialog_loop(self):
        """
        A constant loop which looks at the internal state of the agent, the estimated state of the user and the dialog
        state.

        """
        if self.speak_first:
            self.cns.agent.planned_utterance, self.dialog_ended = self.dm.get_response()
            self.cns.agent.start_time = time.time()
            self.cns.start_speech(self.cns.agent.planned_utterance)

        self.turn_state_history.append(self.BOTH_INACTIVE)
        while not self.dialog_ended:
            time.sleep(self.LOOP_TIME)

            self.trigger_user_turn_on()  # activates self.cns.user_turn_active if relevant

            if self.cns.user_turn_active:
                # The user is active so we wait for vad IPU to trigger
                # to determine EOT
                if not self.cns.vad_ipu_active:
                    self.respond_or_listen()  # predict eot, start_speaking, set cns.user_turn_end_predicted

            if self.cns.agent_speech_ongoing and self.cns.vad_ipu_active:
                if self.is_interrupted():
                    self.should_reapeat()
                    self.cns.stop_speech(False)

            if self.both_inactive or self.only_user_active:
                if self.fallback_inactivity():
                    self.user_turn_off()

            if not self.cns.vad_ipu_active and self.cns.user_turn_end_predicted:
                self.user_turn_off()

            self.update_state()

        print("======== DIALOG LOOP DONE ========")
