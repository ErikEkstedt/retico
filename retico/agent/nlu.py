import requests
import json

URL_SAMPLE = "http://localhost:5000/sample"


def get_sampled_response(text):
    # json_data = {"text": ["Hello there, how can I help you?", "I want to eat food."]}
    json_data = {"text": text}
    response = requests.post(URL_SAMPLE, json=json_data)
    d = json.loads(response.content.decode())
    return d["response"]
