from os import makedirs
from os.path import split
from retico.agent.utils import clean_whitespace, write_json
import time


class StateCommon:
    def __init__(self):
        self.name = ""
        self.utterance = ""
        self.start_time = time.time()

    def __repr__(self):
        s = self.name.upper()
        for k, v in self.__dict__.items():
            s += f"\n{k}: {v}"
        s += "\n" + "-" * 30
        return s

    def finalize(self):
        self.end_time = time.time()

    def norm_time(self, start):
        self.start_time -= start
        self.end_time -= start

    def to_dict(self):
        return self.__dict__


class UserState(StateCommon):
    def __init__(self):
        super().__init__()
        self.name = "user"
        self.prel_utterance = ""
        self.utterance_at_eot = ""
        self.trp_at_eot = -1
        self.all_trps = []

    def norm_time(self, start):
        super().norm_time(start)
        for trp in self.all_trps:
            trp["time"] -= start


class AgentState(StateCommon):
    def __init__(self):
        super().__init__()
        self.name = "agent"
        self.planned_utterance = ""
        self.interrupted = False
        self.completion = 0.0

    def finalize(self):
        super().finalize()
        if self.completion >= 1:
            self.utterance = self.planned_utterance


class Memory:
    def __init__(self):
        self.turns_agent = []
        self.turns_user = []
        self.start_time = 0.0

    def update(self, turn, agent=False):
        if agent:
            self.turns_agent.append(turn)
        else:
            self.turns_user.append(turn)

    def get_turns(self):
        turns = self.turns_agent + self.turns_user
        turns.sort(key=lambda x: x.start_time)
        return turns

    def get_dialog_text(self):
        turns = self.get_turns()

        # utt = str(turns[0].start_time) + turns[0].utterance
        dialog = []
        if len(turns) > 0:
            utt = turns[0].utterance
            last_name = turns[0].name
            for t in turns[1:]:
                if t.utterance == "":
                    continue
                if t.name == last_name:
                    utt = utt + " " + clean_whitespace(t.utterance)
                else:
                    dialog.append(clean_whitespace(utt))
                    # utt = str(t.start_time) + t.utterance
                    utt = clean_whitespace(t.utterance)
                    last_name = t.name
            dialog.append(clean_whitespace(utt))
        return dialog

    def get_dialog_text_debug(self):
        turns = self.get_turns()

        dialog = []
        if len(turns) > 0:
            utt = str(turns[0].start_time) + turns[0].utterance
            last_name = turns[0].name

            for t in turns[1:]:
                if t.name == last_name:
                    utt = utt + " " + str(t.start_time) + t.utterance
                else:
                    dialog.append(clean_whitespace(utt))
                    utt = str(t.start_time) + t.utterance
                    last_name = t.name
            dialog.append(clean_whitespace(utt))
        return dialog

    def finalize_turns(self):
        """
        Finalizes the memory. Sorts the turns in order of appearance and condences turns as necessary.
        """
        turns = []
        for turn in self.get_turns():
            turn.norm_time(self.start_time)
            turns.append(turn.to_dict())
        return turns

    def save(self, savepath):
        data = self.finalize_turns()

        dirpath = split(savepath)[0]
        if dirpath != "":
            makedirs(dirpath, exist_ok=True)
        write_json(data, savepath)
        print("Saved memory -> ", savepath)

    def __repr__(self):
        s = "Memory"
        s += f"\nStart time:  {self.start_time}"
        s += f"\nUser turns:  {len(self.turns_user)}"
        s += f"\nAgent turns: {len(self.turns_agent)}"
        s += f"\nTotal turns: {len(self.turns_user) + len(self.turns_agent)}"
        return s


if __name__ == "__main__":
    import random
    import time

    dialog = ["Hello there how are you doing", "Im great how are you?"]
    memory = Memory()
    memory.start_time = time.time()
    for i in range(10):
        if random.random() < 0.5:
            state = UserState()
            agent = False
        else:
            state = AgentState()
            agent = True
        state.utterance = dialog[i % 2]
        state.start_time = time.time()
        memory.update(state, agent=agent)
        time.sleep(0.01)

    print(memory)
    d = memory.get_dialog_text()
    print()
    print("Dialog text")
    _ = [print(t) for t in d]
