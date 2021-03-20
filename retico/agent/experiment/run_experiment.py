from argparse import ArgumentParser
from os.path import join
from retico.agent.utils import read_json
from subprocess import call

"""
Reads randomized trial orders of interactions and calls the agent script to start the dialog.

The root argument points to the directory in which to store the experiments. 


Given a trials in file `filename` with participant number, `N`, and interaction number, `I` along with args.root the
files from the interaction are saved to /args.root/session_{N}/{policy}

    python experiment/run.py --root /PATH/TO/SAVEDATA --experiment /PATH/TO/EXPERIMENT.json -n participant-number -i interaction-number
    python experiment/run.py --root ~/Experiment --experiment `filename` -n `N` -i `I`

This reads the correct dialog/policy from the file and executes a call to the agent with the correct arguments and root folder
"""

parser = ArgumentParser()
parser.add_argument("--experiment", type=str)
parser.add_argument("-n", "--n", type=int, help="Session / Participant")
parser.add_argument("-i", "--interaction", type=int, help="Interaction number")
parser.add_argument("-nb", "--no_bypass", action="store_true", help="no Bypass")
parser.add_argument(
    "--root", type=str, help="root for agent files", default="/home/erik/Experiment"
)
args = parser.parse_args()

trials = read_json(args.experiment)
interaction = trials[args.n][args.interaction]
dialog = interaction[0]
policy = interaction[1]
root = join(args.root, f"session_{args.n}")
print("ROOT: ", root)


cmd = f"python ../agent.py --root {root} --task {dialog} --policy {policy}"
if args.no_bypass:
    print("#" * 30)
    print("NO BYPASS! WONT WORK ON ZOOM!!!")
    print("#" * 30)
else:
    cmd += " --bypass"

if policy == "prediction":
    cmd += " --short_heuristic_cutoff 1"
    cmd += " --fallback_duration 2"
else:
    cmd += " --fallback_duration 10"


print("=" * 80)
print("Arguments from script")
print(cmd)
print("=" * 80)
cmd = cmd.split()

call(cmd)

print("#" * 70)
print("#" * 70)
print("#" * 70)
print(args.root)
print("#" * 70)
print("#" * 70)
print("#" * 70)
