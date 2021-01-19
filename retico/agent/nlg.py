import json
import requests

URL_SAMPLE = "http://localhost:5000/sample"


class NLG(object):
    def __init__(self, questions=None):
        self.questions = questions
        self.next_question_index = -1

    def generate_response(self, turns):
        json_data = {"text": turns}
        response = requests.post(URL_SAMPLE, json=json_data)
        d = json.loads(response.content.decode())
        return d["response"]

    def get_next_response(self):
        if self.questions is None:
            return "no comment"
        self.next_question_index += 1
        return self.questions[self.next_question_index]
