import threading
import time

from retico.agent.utils import Color as C


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
        self.interuption_ratio = 0.8
        self.repeat_ratio = 0.8

        self.fallback_duration = fallback_duration

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
        elif self.only_agent:
            current_state = self.ONLY_AGENT
        elif self.both_active:
            current_state = self.BOTH_ACTIVE
        else:
            current_state = self.BOTH_INACTIVE

        if self.cns.dialog_states[-1]["state"] != current_state:
            if self.verbose:
                print(C.red + "===" + current_state + "===" + C.end)
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

    def should_repeat(self):
        if self.cns.agent.completion <= self.repeat_ratio:
            self.cns.ask_question_again = True
            if self.verbose:
                print("ask_question_again: True")

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
        else:
            context = self.cns.memory.get_dialog_text()
            (
                planned_utterance,
                self.dialog_ended,
            ) = self.dm.get_response(context)
            self.cns.init_agent_turn(planned_utterance)

    def fallback_inactivity(self):
        """
        If there have been more than `self.fallback_duration` of mutual silence we trigger the agent  to speak

        * Finalize the user
        *
        """
        ret = False
        if not self.cns.vad_turn_active and not self.cns.agent_turn_active:
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
            if latest_activity_time >= self.fallback_duration:
                print("FALLBACK")
                self.cns.finalize_user()
                self.get_response_and_speak()
                ret = True
        return ret

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

    def trigger_user_turn_on(self):
        raise NotImplementedError("trigger_user_turn_on")

    def trigger_user_turn_off(self):
        raise NotImplementedError("trigger_user_turn_off")

    def dialog_loop(self):
        raise NotImplementedError("dialog loop not implemented")
