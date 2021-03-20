import threading
import time

from retico.agent.utils import Color as C


class FrontalCortexBase:
    LOOP_TIME = 0.05  # 50ms  update frequency
    # LOOP_TIME = 0.01  # 50ms  update frequency

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
        fallback_duration=0.7,
        no_input_duration=5,
        no_rank=True,
        verbose=False,
        show_dialog=False,
    ):
        self.cns = central_nervous_system
        self.speak_first = speak_first
        self.no_rank = no_rank
        self.dm = dm
        self.verbose = verbose
        self.show_dialog = show_dialog

        self.dialog_ended = False
        self.suspend = False
        self.interuption_ratio = 0.8
        self.repeat_ratio = 0.8

        self.fallback_duration = fallback_duration
        self.no_input_duration = no_input_duration

        self.last_speaker = None

    @property
    def both_active(self):
        return self.cns.agent_turn_active and self.cns.user_turn_active

    @property
    def both_inactive(self):
        return not self.cns.agent_turn_active and not self.cns.user_turn_active

    @property
    def only_user(self):
        return not self.cns.agent_turn_active and self.cns.user_turn_active

    @property
    def only_agent(self):
        return self.cns.agent_turn_active and not self.cns.user_turn_active

    def update_dialog_state(self):
        if self.only_user:
            current_state = self.ONLY_USER
            self.last_speaker = "user"
        elif self.only_agent:
            current_state = self.ONLY_AGENT
            self.last_speaker = "agent"
        elif self.both_active:
            current_state = self.BOTH_ACTIVE
            self.last_speaker = "both"
        else:
            current_state = self.BOTH_INACTIVE

        if self.cns.dialog_states[-1]["state"] != current_state:
            if self.verbose:
                print(C.red + "===" + current_state + "===" + C.end)
                print(C.blue + "===" + self.last_speaker + "===" + C.end)
            self.cns.dialog_states.append({"state": current_state, "time": time.time()})
            return current_state

        return None

    def check_utterance_dialog_end(self, text=None):
        if "goodbye" in text or "bye" in text:
            return True
        return False

    def is_interrupted(self):
        if self.cns.agent.completion <= self.interuption_ratio:
            if self.verbose:
                print("is_interrupted: True")
            return True
        return False

    def retrigger_user_turn(self):
        if self.verbose:
            print("Retrigger User")

        if self.cns.agent.utterance == "":
            self.cns.dialog_states[-2]["state"] = self.ONLY_USER
            self.cns.dialog_states[-1]["state"] = self.ONLY_USER
        else:
            self.cns.dialog_states[-2]["state"] = self.BOTH_ACTIVE
            self.cns.dialog_states[-1]["state"] = self.BOTH_ACTIVE
        self.cns.init_user_turn(self.cns.memory.turns_user.pop(-1))

    def should_repeat(self):
        if self.cns.agent.completion <= self.repeat_ratio:
            self.cns.ask_question_again = True
            if self.verbose:
                print("Repeat utterance")

    def get_response_and_speak(self, response=None):
        """
        The speak action of the agent.

        * Repeat the last response if necessary
            - if the agent was interrupted while less than `self.repeat_ratio` was completed
        * Query the DM for the next response
        """
        if self.cns.ask_question_again:
            self.cns.init_agent_turn(self.cns.agent.planned_utterance)
        elif response is not None:
            self.cns.init_agent_turn(response)
        elif self.dm is None:
            self.cns.init_agent_turn("This is me talking.")
        elif self.no_rank:
            context, last_speaker = self.cns.memory.get_dialog_text()
            if last_speaker != "user":
                if self.cns.user.utterance != "":
                    context.append(self.cns.user.utterance)
                elif self.cns.user.prel_utterance != "":
                    context.append(self.cns.user.prel_utterance)
            (planned_utterance, self.dialog_ended, data) = self.dm.get_response(
                context, no_rank=True
            )
            self.cns.init_agent_turn(planned_utterance)
        else:
            context, last_speaker = self.cns.memory.get_dialog_text()
            if last_speaker != "user":
                if self.cns.user.utterance != "":
                    context.append(self.cns.user.utterance)
                elif self.cns.user.prel_utterance != "":
                    context.append(self.cns.user.prel_utterance)
            (planned_utterance, self.dialog_ended, data) = self.dm.get_response(context)
            self.cns.init_agent_turn(planned_utterance)
            if data is not None:
                self.cns.user.tokens_on_rank = data["tokens"]
                self.cns.user.eot_on_rank = data["eot"]
                self.cns.user.time_on_rank = data["time"]

    def fallback_inactivity(self):
        """
        If there have been more than `self.fallback_duration` of mutual silence we trigger the agent  to speak
        """

        def both_silent():
            return not self.cns.vad_turn_active and not self.cns.agent_turn_active

        ret = False
        if both_silent():
            now = time.time()
            # the user silence time
            try:  # since last user activity
                user_silence = now - self.cns.vad_turn_off[-1]
            except IndexError:  # if not available count from start of dialog
                user_silence = now - self.cns.start_time

            # The agents silence duration
            try:  # since last agent activity
                agent_silence = now - self.cns.agent_turn_off[-1]
            except IndexError:  # if not available count from start of dialog
                agent_silence = now - self.cns.start_time

            latest_activity_time = min(agent_silence, user_silence)
            if latest_activity_time >= self.fallback_duration and (
                self.last_speaker == "user" or self.last_speaker == "both"
            ):
                print("FALLBACK")
                self.get_response_and_speak()
                self.cns.user.fallback = True
                self.cns.finalize_user()
                ret = True
            elif latest_activity_time > self.no_input_duration:
                print("No INPUT  FALLBACK")
                self.get_response_and_speak()
                self.cns.user.fallback = True
                self.cns.finalize_user()
                ret = True
        return ret

    def trigger_user_turn_on(self):
        """The user turn has started.
        1. a) User turn is OFF
        1. b) The ASR module is OFF -> last_user_asr_active = False
        2. ASR turns on -> now we decode text -> last_user_asr_active = True
        """
        if not self.cns.user_turn_active:
            if self.cns.vad_ipu_active and self.cns.asr_active:
                # print(C.green + "########## FC: user turn ON ########" + C.end)
                self.cns.init_user_turn()

    def start_loop(self):
        """Prepares the dialogue_loop and the DialogueState of the agent and the
        interlocutor by resetting the timers.
        This method starts the dialogue_loop."""
        self.t = threading.Thread(target=self.dialog_loop)
        now = time.time()
        self.cns.start_time = now
        self.cns.memory.start_time = now
        self.t.start()

    def stop_loop(self):
        self.t.join()
        print("Stopped dialog loop")

    def trigger_user_turn_off(self):
        """
        This should be implemented by any specific turn-taking policy
        """
        raise NotImplementedError("trigger_user_turn_off")

    def dialog_loop(self):
        """
        A constant loop which looks at the internal state of the agent, the estimated state of the user and the dialog
        state.

        """
        if self.speak_first:
            planned_utterance, self.dialog_ended, _ = self.dm.get_response()
            print("spoke first")
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
