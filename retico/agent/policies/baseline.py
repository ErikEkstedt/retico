import time

from retico.agent.utils import Color as C
from retico.agent.frontal_cortex import FrontalCortexBase


class FC_Simple(FrontalCortexBase):
    """
    Starts the dialog by speaking its `DUMMY_RESPONSE`. Listens while the user asr is active and only does a fallback
    action which executes the dummy response if the conversation has been inactive for at leat `fallback_duration`
    seconds.

    Never updates the memory...
    """

    INIT_RESPONSE = "Lets start this dialog!"
    FALLBACK_RESPONSE = "This is the inactivity fallback!"

    def dialog_loop(self):
        """
        A constant loop which looks at the internal state of the agent, the estimated state of the user and the dialog
        state.

        """
        if self.speak_first:
            planned_utterance = self.INIT_RESPONSE
            self.cns.init_agent_turn(planned_utterance)

        while not self.dialog_ended:
            time.sleep(self.LOOP_TIME)
            self.fallback_inactivity(self.FALLBACK_RESPONSE)


class FC_Baseline(FrontalCortexBase):
    def trigger_user_turn_off(self):
        ret = False
        if self.cns.user_turn_active:
            if not self.cns.vad_ipu_active and not self.cns.asr_active:
                # print(C.red + "########## FC: user turn off ########" + C.end)
                self.cns.finalize_user()
                ret = True
        return ret

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

        print("======== DIALOG DONE ========")
