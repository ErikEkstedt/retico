import requests
import json

QUESTIONS = [
    {
        "question": "Hello there, how are you doing today?",
        "follow_ups": [
            "That's great, did you sleep well?",
            "I'm sorry to hear that, what's wrong?",
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

URL_RANK = "http://localhost:5000/response_ranking"


class DM:
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

    def select_response(self, context, responses):
        json_data = {"context": context, "responses": responses}
        response = requests.post(URL_RANK, json=json_data)
        d = json.loads(response.content.decode())
        return d["response"]

    def next_question(self, context=None):
        if context is None:  # we always start with the first question
            self.current_question = self.questions.pop(0)
            self.current_follow_ups = self.current_question["follow_ups"]
            self.main_question_idx = 0
            self.n_current_follow_ups = 0
            return self.current_question["question"]
        else:
            # If we have asked the minimum amount of follow ups we select a new main question
            if self.n_current_follow_ups >= self.n_follow_ups:
                print("New Main Question")
                main_questions = [q["question"] for q in self.questions]
                q_to_ind = {q: i for i, q in enumerate(main_questions)}

                response = self.select_response(context, main_questions)
                self.current_question = self.questions.pop(q_to_ind[response])
                self.current_follow_ups = self.current_question["follow_ups"]
                self.n_current_follow_ups = 0
                print("Follow ups: ", self.current_follow_ups)
                return response
            else:
                # follow up
                print("New Follow up Question")
                q_to_ind = {q: i for i, q in enumerate(self.current_follow_ups)}

                response = self.select_response(context, self.current_follow_ups)
                self.current_follow_ups.pop(q_to_ind[response])  # remove the follow up
                self.n_current_follow_ups += 1
                print("Follow ups: ", self.current_follow_ups)
                return response


if __name__ == "__main__":

    dm = DM()

    dm.next_question()

    dm.next_question("hello")
    dm.next_question("hello")
    dm.next_question("hello")
    dm.next_question("hello")
    dm.next_question("hello")

    q = QUESTIONS.copy()
    print(len(q))
    current_questions = q.pop(0)
    current_main = current_questions["question"]
    current_follow_ups = current_questions["follow_ups"]
    print("total: ", len(q))
    print("current_follow_ups: ", len(current_follow_ups))
