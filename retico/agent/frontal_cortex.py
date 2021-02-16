import threading
import time


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
        if self.cns.agent.completion <= self.interuption_ratio:
            if self.verbose:
                print("is_interrupted: True")
            return True
        return False

    def should_reapeat(self):
        if self.cns.agent.completion <= self.repeat_ratio:
            self.cns.ask_question_again = True
            if self.verbose:
                print("ask_question_again: True")

    def speak(self, response=None):
        """
        The speak action of the agent.

        * Repeat the last response if necessary
            - if the agent was interrupted while less than `self.repeat_ratio` was completed
        * Query the DM for the next response
        """
        if response is not None:
            self.cns.start_speech(response)
        elif self.cns.ask_question_again:
            self.cns.start_speech()
        else:
            context = self.cns.memory.get_dialog_text()
            self.cns.agent.start_time = time.time()
            (
                self.cns.agent.planned_utterance,
                self.dialog_ended,
            ) = self.dm.get_response(context)
            self.cns.start_speech(self.cns.agent.planned_utterance)

    def fallback_inactivity(self, response=None):
        """
        If there have been more than `self.fallback_duration` of mutual silence we trigger the agent  to speak

        * Finalize the user
        *
        """
        ret = False
        if not self.cns.vad_base_active:
            now = time.time()
            try:
                user_silence = now - self.cns.user.vad_base_off[-1]
            except IndexError:
                user_silence = now - self.cns.user_last_asr_end_time
            agent_silence = now - self.cns.agent_last_speech_end_time
            latest_activity_time = min(agent_silence, user_silence)
            if latest_activity_time >= self.fallback_duration:
                print("FALLBACK")
                self.cns.finalize_user()
                self.speak()
                ret = True
        return ret

    def dialog_loop(self):
        raise NotImplementedError("dialog loop not implemented")

    def start_loop(self):
        """Prepares the dialogue_loop and the DialogueState of the agent and the
        interlocutor by resetting the timers.
        This method starts the dialogue_loop."""
        self.t = threading.Thread(target=self.dialog_loop)
        now = time.time()
        self.cns.user.asr_end_time = now
        self.cns.memory.start_time = now
        self.t.start()

    def stop_loop(self):
        self.t.join()
        print("Stopped dialog loop")
