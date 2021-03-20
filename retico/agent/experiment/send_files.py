from os.path import join, abspath, expanduser, isfile, split, basename
from os import listdir, walk
from subprocess import call
from glob import glob
import sys
from tqdm import tqdm

TO = "KTHStation:ExperimentTest2"

assert len(sys.argv) > 1, "must provide input"
print("1: ", sys.argv[1])

from_path = sys.argv[1]

# from_path = "~/projects/retico/retico/agent/data/experiment_test/experiment_erik_local"
print(from_path)
if "~" in from_path:
    from_path = from_path.replace("~", expanduser("~"))

print(from_path)

# ['hparams.json', 'annotation.json', 'dialog.wav', 'dialog.json']

session = split(from_path)[-1]

cmd = 'rsync -r --exclude="*_audio.wav" {root} {to_path}'


# for root, dirs, files in walk(from_path):
#     print("root: ", root)
#     print("dirs: ", dirs)
#     print("files: ", files)
#     print()
# print(glob(join(from_path, "*")))


# find . -maxdepth 1 -type f -not \( -name \*foo\* -o -name \*bar\* \) | xargs -I{} scp {} username@otherserver:
# find /home/erik/projects/retico/retico/agent/data/experiment_test/experiment_erik_local -maxdepth 2 -type f -not \( -name \*foo\* -o -name \*bar\* \) | xargs -I{} scp {} KTHStation:ExperimentTest2
