import json
import re
from datetime import datetime
from os import listdir, makedirs
from os.path import join


class Color:
    """
    Used to color the output text when debugging or printing out dialogs
    """

    grey = "\033[90m"
    red = "\033[91m"
    green = "\033[92m"
    yellow = "\033[93m"
    blue = "\033[94m"
    pink = "\033[95m"
    cyan = "\033[96m"
    end = "\033[0m"


def write_json(data, filename):
    with open(filename, "w", encoding="utf-8") as jsonfile:
        json.dump(data, jsonfile, ensure_ascii=False)


def read_json(path, encoding="utf8"):
    with open(path, "r", encoding=encoding) as f:
        data = json.loads(f.read())
    return data


def clean_whitespace(s):
    s = re.sub("^\s", "", s)
    s = re.sub("$\s", "", s)
    s = re.sub("\s\s+", " ", s)
    return s


def create_session_dir(root):
    """
    Creates a directory at root given todays date. session name is simply the number of files present in the date
    directory.

    $root/YY_MM_DD/0/
    $root/YY_MM_DD/1/
    $root/YY_MM_DD/.../
    $root/YY_MM_DD/N/
    """
    date = datetime.today().strftime("%Y_%m_%d")  # todays date
    session_dir = join(root, date)
    # must create this first to count if sessions already exists
    makedirs(session_dir, exist_ok=True)
    session = len(listdir(session_dir))  # session of the day
    session_dir = join(session_dir, str(session))
    makedirs(session_dir, exist_ok=True)  # create session
    return session_dir
