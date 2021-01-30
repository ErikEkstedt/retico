import json
import random
import requests
import threading
import time

from retico.agent.utils import clean_whitespace, Color as C

URL_TRP = "http://localhost:5000/trp"


class FrontalCortexBase:
    LOOP_TIME = 0.05  # 50ms  update frequency

    # turn states
    BOTH_ACTIVE = "double_talk"
    BOTH_INACTIVE = "silence"
    ONLY_USER = "only_user"
    ONLY_AGENT = "only_agent"

    def __init__(
        self,
        central_nervous_system,
        dm=None,
        speak_first=True,
        fallback_duration=4,
        verbose=False,
    ):
        self.cns = central_nervous_system
        self.speak_first = speak_first
        self.dm = dm
        self.verbose = verbose

        self.dialog_ended = False
        self.suspend = False

        self.fallback_duration = fallback_duration

    @property
    def both_inactive(self):
        raise NotImplementedError("")

    @property
    def both_active(self):
        raise NotImplementedError("")

    @property
    def only_user_active(self):
        raise NotImplementedError("")

    @property
    def only_agent_active(self):
        raise NotImplementedError("")

    def check_utterance_dialog_end(self, text=None):
        if "goodbye" in text or "bye" in text:
            return True
        return False

    def is_interrupted(self):
        if self.cns.agent.completion < 0.8:
            return True
        return False

    def fallback_inactivity(self, response=None):
        now = time.time()
        agent_silence = now - self.cns.agent_last_speech_end_time
        user_silence = now - self.cns.user_last_asr_end_time
        latest_activity_time = min(agent_silence, user_silence)
        if latest_activity_time >= self.fallback_duration:
            print("FALLBACK")
            if response is None:
                context = self.cns.memory.get_dialog_text()
                self.cns.agent.start_time = time.time()
                (
                    self.cns.agent.planned_utterance,
                    self.dialog_ended,
                ) = self.dm.get_response(context)
                self.cns.start_speech(self.cns.agent.planned_utterance)
            else:
                self.cns.start_speech(response)
            self.cns.finalize_user()

    def dialog_loop(self):
        raise NotImplementedError("dialog loop not implemented")

    def start_loop(self):
        """Prepares the dialogue_loop and the DialogueState of the agent and the
        interlocutor by resetting the timers.
        This method starts the dialogue_loop."""
        t = threading.Thread(target=self.dialog_loop)
        now = time.time()
        self.cns.user.asr_end_time = now
        self.cns.memory.start_time = now
        t.start()


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
        self.cns.user_turn_active = self.cns.user_asr_active
        self.cns.user_last_turn_end_time = self.cns.user_last_asr_end_time

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
        if end:
            self.dialog_ended = True
        else:
            context = self.cns.memory.get_dialog_text()
            (
                self.cns.agent.planned_utterance,
                self.dialog_ended,
            ) = self.dm.get_response(context)
            self.cns.start_speech(self.cns.agent.planned_utterance)

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

                elif last_state == self.ONLY_AGENT:
                    self.cns.finalize_agent()
                else:
                    self.fallback_inactivity()
                last_state = self.BOTH_INACTIVE

            elif self.both_active:
                if self.verbose and last_state != self.BOTH_ACTIVE:
                    print(C.red + "DOUBLE TALK" + C.end)

                if last_state == self.ONLY_AGENT:
                    if self.is_interrupted():
                        self.cns.stop_speech()
                elif last_state == self.ONLY_USER:
                    finalize = True
                    if self.cns.agent.completion < 0.2:
                        finalize = False
                    self.cns.stop_speech(finalize)

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


class FC_EOT(FrontalCortexBase):
    def __init__(self, dm, trp_threshold=0.1, backchannel_prob=0.4, **kwargs):
        super().__init__(**kwargs)
        self.dm = dm
        self.trp_threshold = trp_threshold
        self.backchannel_prob = backchannel_prob

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
        return not self.cns.user_turn_active and self.cns.agent_speech_ongoing

    def lm_eot(self, text):
        json_data = {"text": text}
        response = requests.post(URL_TRP, json=json_data)
        d = json.loads(response.content.decode())
        return d["trp"][-1]  # only care about last token

    def respond_or_listen(self):
        context = self.cns.memory.get_dialog_text()
        current_utt = clean_whitespace(self.cns.user.utterance)
        context.append(current_utt)

        if self.check_utterance_dialog_end(current_utt):
            self.dialog_ended = True
        else:
            for i, utt in enumerate(context):
                if i % 2 == 0:
                    print(C.blue + utt, C.end)
                else:
                    print(C.yellow + utt, C.end)

            trp = self.lm_eot(context)

            if trp >= self.trp_threshold:
                print(C.green + f"EOT recognized: {round(trp, 3)}" + C.end)
                self.cns.finalize_user()
                self.cns.user_turn_active = False
                self.cns.agent.start_time = time.time()

                (
                    self.cns.agent.planned_utterance,
                    self.dialog_ended,
                ) = self.dm.get_response(context)
                self.cns.start_speech(self.cns.agent.planned_utterance)
            else:
                print(C.red + f"listen: {1-round(trp, 3)}" + C.end)
                if random.random() <= self.backchannel_prob:
                    self.cns.backchannel("Go on.")

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
                    end = self.respond_or_listen()
                    if end:
                        print("END EVERYTHING")
                        self.dialog_ended = True
                        break
                elif last_state == self.ONLY_AGENT:
                    self.cns.finalize_agent()
                else:
                    self.fallback_inactivity()
                last_state = self.BOTH_INACTIVE

            elif self.both_active:
                if self.verbose and last_state != self.BOTH_ACTIVE:
                    print(C.red + "DOUBLE TALK" + C.end)

                if last_state == self.ONLY_AGENT:
                    if self.is_interrupted():
                        self.cns.stop_speech()
                elif last_state == self.ONLY_USER:
                    finalize = True
                    if self.cns.agent.completion < 0.2:
                        finalize = False
                    self.cns.stop_speech(finalize)

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
