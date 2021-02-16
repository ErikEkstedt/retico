import time

from retico.agent.utils import Color as C
from retico.agent.frontal_cortex import FrontalCortexBase


class SimpleFC(FrontalCortexBase):
    """
    Starts the dialog by speaking its `DUMMY_RESPONSE`. Listens while the user asr is active and only does a fallback
    action which executes the dummy response if the conversation has been inactive for at leat `fallback_duration`
    seconds.

    Never updates the memory...
    """

    INIT_RESPONSE = "Lets start this dialog!"
    FALLBACK_RESPONSE = "This is the inactivity fallback!"

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

    def dialog_loop(self):
        """
        A constant loop which looks at the internal state of the agent, the estimated state of the user and the dialog
        state.

        """
        if self.speak_first:
            if self.dm is not None:
                self.cns.agent.planned_utterance = self.dm.next_question()
            else:
                self.cns.agent.planned_utterance = self.INIT_RESPONSE
            self.cns.start_speech(self.cns.agent.planned_utterance)

        last_state = None
        while not self.dialog_ended:
            time.sleep(self.LOOP_TIME)

            if self.suspend:
                continue

            if self.both_inactive:
                if self.verbose and last_state != "both_inactive":
                    print("BOTH INACTIVE")
                    last_state = "both_inactive"
                self.fallback_inactivity(self.FALLBACK_RESPONSE)
            elif self.both_active:
                if self.verbose and last_state != "double_talk":
                    print("DOUBLE TALK")
                    last_state = "double_talk"
            elif self.only_user_active:
                if self.verbose and last_state != "only_user":
                    print("USER")
                    last_state = "only_user"
            else:
                if self.verbose and last_state != "only_agent":
                    print("AGENT")
                    last_state = "only_agent"


class FC_Baseline(FrontalCortexBase):
    def __init__(self, dm, **kwargs):
        super().__init__(**kwargs)
        self.dm = dm

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

    def respond_or_listen(self):
        end = self.check_utterance_dialog_end(self.cns.user.utterance)
        self.cns.finalize_user()
        self.cns.init_user_turn()
        if end:
            self.dialog_ended = True
        else:
            self.speak()

    def dialog_loop(self):
        """
        A constant loop which looks at the internal state of the agent, the estimated state of the user and the dialog
        state.

        """
        if self.speak_first:
            self.cns.agent.planned_utterance, self.dialog_ended = self.dm.get_response()
            self.cns.start_speech(self.cns.agent.planned_utterance)

        last_state = "both_inactive"
        while not self.dialog_ended:
            time.sleep(self.LOOP_TIME)

            if self.both_inactive:
                if self.verbose and last_state != self.BOTH_INACTIVE:
                    print(C.red + "BOTH INACTIVE" + C.end)

                if last_state == self.ONLY_USER:
                    self.respond_or_listen()
                else:
                    self.fallback_inactivity()
                last_state = self.BOTH_INACTIVE

            elif self.both_active:
                if self.verbose and last_state != self.BOTH_ACTIVE:
                    print(C.red + "DOUBLE TALK" + C.end)

                if last_state == self.ONLY_AGENT:
                    if self.is_interrupted():
                        self.should_reapeat()
                        self.cns.stop_speech(False)
                last_state = self.BOTH_ACTIVE

            elif self.only_user_active:
                if self.verbose and last_state != self.ONLY_USER:
                    print(C.red + "USER" + C.end)
                last_state = self.ONLY_USER
            else:
                if self.verbose and last_state != self.ONLY_AGENT:
                    print(C.red + "AGENT" + C.end)
                last_state = self.ONLY_AGENT
        print("======== DIALOG DONE ========")
