import requests
import json
import random

from retico.agent.utils import read_json

QUESTIONS = [
    {
        "question": "Hello there, how are you doing today?",
        "follow_ups": [
            "That's great, did you sleep well?",
            "I'm happy to hear that, go on",
            "That's too bad, what is wrong?",
            # "I'm sorry to hear that, what is wrong?",
            "Well tomorrow is another day. Do you have any plans?",
            "great, tell me more",
        ],
    },
    {
        "question": "Do you exercise regularly?",
        "follow_ups": [
            "What kind of exercise is your favorite",
            "Have you ever done yoga?",
            "Do you thinks it's a good idea to get more exercise?",
            "I love to run, do you?",
        ],
    },
    {
        "question": "Are you a healthy eater?",
        "follow_ups": [
            "What's your favorite meal?",
            "How often do you eat pizza?",
            "How many times a week do eat comfort food",
            "What did you eat for breakfast?",
        ],
    },
    {
        "question": "Tell me about your life",
        "follow_ups": [
            "Do you have any hobbies?",
            "What do you like to do in your spare time?",
            "Are you single?",
            "Are happy with your life in general?",
        ],
    },
    {
        "question": "That was all that I had to ask, goodbye!",
        "follow_ups": [
            "Bye bye",
            "See you later gater",
            "toot toot there goes the train",
        ],
    },
]

URL_SAMPLE = "http://localhost:5001/sample"
URL_RANK = "http://localhost:5001/response_ranking"


class DMBase:
    def rank_responses(self, context, responses):
        json_data = {"context": context, "responses": responses}
        response = requests.post(URL_RANK, json=json_data)
        d = json.loads(response.content.decode())
        return d["response"]


class DM(DMBase):
    def __init__(self, questions=None, n_follow_ups=2):
        if questions is None:
            questions = QUESTIONS.copy()

        self.n_follow_ups = n_follow_ups
        self.original_questions = questions

        self.questions = questions
        self.current_question = -1
        self.n_current_follow_ups = -1

        self.initial_question_ind = 0
        self.main_question_idx = 0
        self.n_current_follow_ups = 0

    def get_response(self, context=None):
        if context is None:  # we always start with the first question
            self.current_question = self.questions.pop(0)
            self.current_follow_ups = self.current_question["follow_ups"]
            self.main_question_idx = 0
            self.n_current_follow_ups = 0
            response = self.current_question["question"]
            end = False
        else:
            # If we have asked the minimum amount of follow ups we select a new main question
            if len(self.questions) == 0:
                response = "Dialog Done"
                end = True
            else:
                if self.n_current_follow_ups >= self.n_follow_ups:
                    # print("New Main Question")
                    main_questions = [q["question"] for q in self.questions]
                    q_to_ind = {q: i for i, q in enumerate(main_questions)}

                    response = self.rank_responses(context, main_questions)
                    self.current_question = self.questions.pop(q_to_ind[response])
                    self.current_follow_ups = self.current_question["follow_ups"]
                    self.n_current_follow_ups = 0
                    # print("Follow ups: ", self.current_follow_ups)
                    end = False
                else:
                    # follow up
                    # print("New Follow up Question")
                    q_to_ind = {q: i for i, q in enumerate(self.current_follow_ups)}

                    response = self.rank_responses(context, self.current_follow_ups)
                    self.current_follow_ups.pop(
                        q_to_ind[response]
                    )  # remove the follow up
                    self.n_current_follow_ups += 1
                    # print("Follow ups: ", self.current_follow_ups)
                    end = False
        return response, end


class DM_LM(object):
    def __init__(self, initial_utterance="Hello there, how can I help you?"):
        self.initial_utterance = initial_utterance

    def get_response(self, turns=None):
        end = False
        if turns is None:
            utterance = self.initial_utterance
        else:
            json_data = {"text": turns}
            response = requests.post(URL_SAMPLE, json=json_data)
            d = json.loads(response.content.decode())
            utterance = d["response"]
        return utterance, end


class DMExperiment(DMBase):
    TASKS = ["exercise", "food", "hobbies"]

    acknowledgements = [
        "I see.",
        "alright.",
        "okay",
        "",
    ]
    segways = ["so,", "", "yeah,", "lets see,"]
    answers = [
        # "I can't answer that question. Can we continue with the interview?",
        # "I can't answer any questions. Shall we continue?",
    ]

    ExercisePath = "/home/erik/projects/retico/retico/agent/dm/dialogs/exercise.json"
    FoodPath = "/home/erik/projects/retico/retico/agent/dm/dialogs/food.json"
    HobbiesPath = "/home/erik/projects/retico/retico/agent/dm/dialogs/hobbies.json"

    def __init__(self, task):
        assert task in self.TASKS, f"Please choose task in {self.TASKS}"
        self.task = task
        self.dialog = self._load_dialogs()

        self.randomize_seqway = True
        self.randomize_acknowledgements = True
        self.response_count = 0
        self.short_heuristic_cutoff = 3

    def _load_dialogs(self):
        if self.task == "exercise":
            dialog = read_json(self.ExercisePath)
        elif self.task == "food":
            dialog = read_json(self.FoodPath)
        else:
            dialog = read_json(self.HobbiesPath)
        return dialog

    def get_questions(self):
        questions = self.dialog["short"] + self.dialog["long"]
        # print("questions: ", len(questions))
        if len(questions) > 0:
            questions += self.answers
        return questions

    def pop_response(self, response):
        kind = None
        pop_index = 1
        for i, question in enumerate(self.dialog["short"]):
            if response == question:
                kind = "short"
                pop_index = i
                break

        if kind is None:
            for i, question in enumerate(self.dialog["long"]):
                if response == question:
                    kind = "long"
                    pop_index = i

        if kind is None:
            for i, question in enumerate(self.answers):
                if response == question:
                    kind = "answers"
                    pop_index = i

        if kind is not None:
            if kind == "answers":
                self.answers.pop(pop_index)
            else:
                self.dialog[kind].pop(pop_index)

    def get_response(self, context=None):
        end = False
        if self.response_count == 0:
            response = self.dialog["introduction"][0]
        else:
            assert context is not None, "context is None..."

            current_user_turn = context[-1]

            if (
                self.response_count > 1
                and len(current_user_turn.split()) <= self.short_heuristic_cutoff
            ):
                response = "Could you please elaborate on that"
                end = False
            else:
                questions = self.get_questions()
                if len(questions) > 0:
                    # acknowledgement
                    if self.randomize_acknowledgements:
                        ack = random.choice(self.acknowledgements)
                    else:
                        ack = self.rank_responses(context, self.acknowledgements)

                    if self.randomize_seqway:
                        segway = random.choice(self.segways)
                    else:
                        segs = [ack + " " + s for s in self.segways]
                        segway = self.rank_responses(context, segs)

                    response = self.rank_responses(context, questions)
                    self.pop_response(response)  # remove response
                    response = segway + " " + response
                else:
                    response = "Thank you for answering my questions. This session is over. Goodbye."
                    end = True
        self.response_count += 1
        return response, end


if __name__ == "__main__":

    # dm = DM()
    dm = DMExperiment(task="exercise")
    print(len(dm.dialog["long"]) + len(dm.dialog["short"]))
    response, end = dm.get_response()
    print("response: ", response)
    print(len(dm.dialog["long"]) + len(dm.dialog["short"]))
    response, end = dm.get_response(context=[response, "yes"])
    print("response: ", response)
    print(len(dm.dialog["long"]) + len(dm.dialog["short"]))

    dm.get_response("hello")
    dm.get_response("hello")
    dm.get_response("hello")
    dm.get_response("hello")

    q = QUESTIONS.copy()
    print(len(q))
    current_questions = q.pop(0)
    current_main = current_questions["question"]
    current_follow_ups = current_questions["follow_ups"]
    print("total: ", len(q))
    print("current_follow_ups: ", len(current_follow_ups))
