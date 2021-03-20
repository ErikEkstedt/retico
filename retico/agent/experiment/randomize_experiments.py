import random
from collections import Counter
from numpy.random import choice
from retico.agent.utils import write_json


"""
Randomize experiment.

The experiment is conducted by letting participants interact with a SDS. There are three different policies we wish to
study using three different dialog setups. A session defines three interactions with the agent using the three different
policies and dialogs. Given the number of dialogs and policies we get 9 possible unique interactions.

Interactions:

('A', 'X'), ('A', 'Y'), ('A', 'Z')
('B', 'X'), ('B', 'Y'), ('B', 'Z')
('C', 'X'), ('C', 'Y'), ('C', 'Z')

Each session must contain X,Y,Z and A,B,C but combined in different ways which makes up 6 possible configurations listed
in SESSIONS. This means that if the number of participants is perfectly divisible by 6 we get a uniform spread of
interactions.

We randomize the sessions by first chosing the largest uniform configurations that is possible (N//6) and the remaining
sessions are drawn randomly from the possible sessions.
"""

SESSIONS = [
    [("A", "X"), ("B", "Y"), ("C", "Z")],
    [("A", "X"), ("B", "Z"), ("C", "Y")],
    [("A", "Y"), ("B", "Z"), ("C", "X")],
    [("A", "Y"), ("B", "X"), ("C", "Z")],
    [("A", "Z"), ("B", "X"), ("C", "Y")],
    [("A", "Z"), ("B", "Y"), ("C", "X")],
]
N_EQUAL = len(SESSIONS)

policies = {"X": "baseline", "Y": "baselineVad", "Z": "prediction"}
dialogs = {"A": "travel_a", "B": "travel_b", "C": "travel_c"}


def sample_sessions(N):
    n = N // N_EQUAL  # uniform
    r = N % N_EQUAL  # remainder
    experiments = SESSIONS * n
    for i in list(choice(range(r), size=r, replace=False)):
        experiments.append(SESSIONS[i])
    return experiments


def sample_experiment(N, shuffle_session_order=True, shuffle_interaction_order=True):
    experiment = sample_sessions(N)
    if shuffle_session_order:
        random.shuffle(experiment)

    if shuffle_interaction_order:
        for session in experiment:
            random.shuffle(session)
    return [tuple(session) for session in experiment]


def sanity_check(experiment):
    """
    SANITY CHECK
    Count the session/interactions
    """

    def get_abc_xyz_counters(experiment):
        abcs = set()
        xyzs = set()
        for session in experiment:
            for interaction in session:
                abcs.update([interaction[0]])
                xyzs.update([interaction[1]])
        abc = {aa: 0 for aa in abcs}
        xyz = {xx: 0 for xx in xyzs}
        return abc, xyz

    abc, xyz = get_abc_xyz_counters(experiment)
    for session in experiment:
        for interaction in session:
            abc[interaction[0]] += 1
            xyz[interaction[1]] += 1
    c = Counter(experiment)
    print("\nTotal session count")
    print("-------------------")
    for session, count in c.items():
        print(f"{count}: {session}")
    print("\nTotal policy count")
    print("-------------------")
    for p, count in xyz.items():
        print(f"{p}: {count}")
    print("\nTotal dialog count")
    print("-------------------")
    for p, count in abc.items():
        print(f"{p}: {count}")


def to_named(experiment):
    named_experiment = []
    for session in experiment:
        named_experiment.append(
            tuple(((dialogs[abc], policies[xyz]) for abc, xyz in session))
        )
    return named_experiment


def try_it():
    N = 17
    experiment = sample_experiment(N)
    sanity_check(experiment)

    experiment = to_named(experiment)
    sanity_check(experiment)

    filename = "/tmp/experiment.json"
    write_json(experiment, filename)


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument(
        "-N", "--n_participants", type=int, help="Number of participants"
    )
    parser.add_argument(
        "--not_named",
        action="store_true",
        help="Get back A,B,C and X,Y,Z instead of names of dialog/policies",
    )
    parser.add_argument(
        "--filename",
        type=str,
        default=None,
        help="filename to store json file of experiment",
    )
    args = parser.parse_args()
    print(args)

    experiment = sample_experiment(args.n_participants)
    sanity_check(experiment)

    if not args.not_named:
        experiment = to_named(experiment)
        print("\n" + "=" * 70)
        sanity_check(experiment)

    if args.filename is not None:
        write_json(experiment, args.filename)
        print("Saved json file -> ", args.filename)
