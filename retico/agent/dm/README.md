# Dialog Manager

The dialog manager in this project is very minimalistic. It uses a collection of predefined questions and uses an external ranker (Neural Network) to choose responses. The DM keeps track of which questions have already been executed and informs when there are no questions left.


* [ ] Rank segway and question
* [ ] stucture dialog


## Dialog

For the purpose of evaluating incremental turn-taking we desire some special properties of our questions. We want the ability to illicit longer/shorter responses and provide acknowledgements/segways from a user response to another question.

```
                              Positive acknowledgement
Question -> User response ->                            -> Question
                              Negative acknowledgement
```

### What should the dialog be about?

General such that every user may provide useful responses. Talk about daily life with a focus on exercise, mental health and nutrition.


### Question that illicit longer responses

* Open ended
  * How/what
      * citation
  * "Please tell me about what makes you happy"
  * "Tell me about your life"
  * "Please you tell me about your weekly exercise routine?"
  * "Please tell me about your family"

### Question that illicit shorter responses

* Yes/no
  * "Can you hear me?"
  * "Are you ready to answer some questions?"
* Finite choice
  * "do you prefer dogs or cats?"
  * "which exercise do you like best, running or yoga?"
  * "How many siblings do you have?"

### Acknowledgement/Segway

**Positive:**
* "That's great"
* "Fantastic"

**Negative:**
* "oh no"
* "That sounds aweful"

Neutral 
* "ok"
* "thank you"
* "I see"
* "I understand"


### General Follow-ups

General follow up questions which can be asked at any time.

* "Please tell me more"
* "Could you be more specific?"


### Answers to questions

* "I'm sorry I can't answer that"

## Ranking

Given "complete" agent turns the ranker simply selects the most likely response. However, if each turn should consist of a seqway and a question we could do it in two different ways.

* Sequentially
  * Rank the segway first
  * Select the segway
  * Rank the questions
  * Select question
* Batchify
  * Rank all possible permutations
  * Select best collection

Start with sequentially $\to$ 2 forward passes in the model.
