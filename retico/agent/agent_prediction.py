import requests
import json
import time

from retico.agent.CNS import CentralNervousSystem
from retico.agent.agent import FrontalCortexBase
from retico.agent.utils import clean_whitespace, Color as C

URL_Prediction = "http://localhost:5000/prediction"


class CNS_Continuous(CentralNervousSystem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user_turn_end_predicted = False

    def asr(self, input_iu):
        """Process the ASR input"""

        # Activate user-asr state
        if not self.user_asr_active:
            self.user_asr_active = True
            self.user.asr_start_time = time.time()
            if self.verbose:
                print(C.yellow + f"ASR Onset: {self.user_asr_active}" + C.end)

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
                self.user.end_time = now
                self.finalize_user()
                self.user_turn_end_predicted = False

            # if self.
            if self.verbose:
                print(C.yellow + "ASR Final updated last" + C.end)


class FC_Predict(FrontalCortexBase):
    """
    Starts the dialog by speaking its `DUMMY_RESPONSE`. Listens while the user asr is active and only does a fallback
    action which executes the dummy response if the conversation has been inactive for at leat `fallback_duration`
    seconds.
    """

    def __init__(self, dm, trp_threshold=0.1, **kwargs):
        super().__init__(**kwargs)
        self.dm = dm
        self.trp_threshold = trp_threshold

        self.last_context = ""
        self.last_current_utterance = ""
        self.last_user_asr_active = False

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

    def fast_eot(self):
        current_utt = clean_whitespace(self.cns.user.prel_utterance)

        if current_utt != "" and current_utt != self.last_current_utterance:
            print(C.yellow + "Fast REACTION" + C.end)

            self.last_current_utterance = current_utt
            context = self.cns.memory.get_dialog_text()
            context.append(current_utt)

            res = self.lm_prediction(context)
            trp = res["p"]

            if self.verbose:
                for i, utt in enumerate(context[:-1]):
                    if i % 2 == 0:
                        print(C.blue + utt, C.end)
                    else:
                        print(C.yellow + utt, C.end)

            # If we predict a turn-shift we query the DM and initiate speech
            if trp >= self.trp_threshold:
                if self.verbose:
                    print(C.yellow + current_utt + C.green + f" -> ## {trp} ##" + C.end)
                    print("-" * 50)
                self.cns.agent.start_time = time.time()
                (
                    self.cns.agent.planned_utterance,
                    self.dialog_ended,
                ) = self.dm.get_response(context)
                self.cns.start_speech(self.cns.agent.planned_utterance)
                self.cns.user_turn_end_predicted = True
            else:
                if self.verbose:
                    print(C.yellow + current_utt + C.red + f" -> ## {trp} ##" + C.end)
                    print("-" * 50)
                self.cns.user_turn_end_predicted = False

    def user_turn_on(self):
        """The user turn has started.
        1. a) User turn is OFF
        1. b) The ASR module is OFF -> last_user_asr_active = False
        2. ASR turns on -> now we decode text -> last_user_asr_active = True
        """
        if not self.cns.user_turn_active:
            if not self.last_user_asr_active and self.cns.user_asr_active:
                print(C.green + "########## ON user state ########" + C.end)
                self.cns.user.start_time = time.time()
                self.cns.user_turn_active = True
                self.last_user_asr_active = True

    def user_turn_off(self):
        pass

    def dialog_loop(self):
        """
        A constant loop which looks at the internal state of the agent, the estimated state of the user and the dialog
        state.

        """
        if self.speak_first:
            self.cns.agent.planned_utterance, self.dialog_ended = self.dm.get_response()
            self.cns.agent.start_time = time.time()
            self.cns.start_speech(self.cns.agent.planned_utterance)

        self.turn_state_history.append("both_inactive")
        while not self.dialog_ended:
            time.sleep(self.LOOP_TIME)

            self.user_turn_on()  # activates self.cns.user_turn_active if relevant

            ################ ONLY USER   ###################
            if self.only_user_active:
                if self.verbose and self.turn_state_history[-1] != self.ONLY_USER:
                    print(C.red + "USER" + C.end)

                # Predict upcomming EOT
                if not self.cns.vad_ipu_active:
                    self.fast_eot()  # predict eot, start_speaking, set cns.user_turn_end_predicted

                self.turn_state_history.append(self.ONLY_USER)

            elif self.both_inactive:
                if self.verbose and self.turn_state_history[-1] != self.BOTH_INACTIVE:
                    print(C.red + "BOTH INACTIVE" + C.end)

                if self.turn_state_history[-1] == self.BOTH_INACTIVE:
                    self.fallback_inactivity()

                self.turn_state_history.append(self.BOTH_INACTIVE)

            ################ DOUBLE TALK ###################
            elif self.both_active:
                if self.verbose and self.turn_state_history[-1] != self.BOTH_ACTIVE:
                    print(C.red + "DOUBLE TALK" + C.end)

                ###################
                ## AGENT -> BOTH ##
                ###################
                if self.turn_state_history[-1] == self.ONLY_AGENT:
                    pass
                    # if self.is_interrupted():
                    #     self.cns.stop_speech()
                ###################
                ## USER -> BOTH ##
                ###################
                elif self.turn_state_history[-1] == self.ONLY_USER:
                    # do nothgin right now to see if overlaps is a problem
                    pass
                    # if self.cns.agent.completion < 0.2:
                    #     finalize = False
                    # self.cns.stop_speech(finalize)

                self.turn_state_history.append(self.BOTH_ACTIVE)
            ################ ONLY AGENT  ###################
            else:
                if self.verbose and self.turn_state_history[-1] != self.ONLY_AGENT:
                    print(C.red + "AGENT" + C.end)
                self.turn_state_history.append(self.ONLY_AGENT)

        print("======== DIALOG DONE ========")
