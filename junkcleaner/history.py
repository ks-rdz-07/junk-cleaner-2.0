"""Activity history: every scan, cleanup, quarantine action and security check, one JSON object per line."""
import json
import os
import time

from .platform_os import DATA_DIR

PATH = os.path.join(DATA_DIR, "history.jsonl")
MAX = 5000  # newest entries shown


def log(kind, summary, **details):
    """kind: Scan, Clean, Quarantine, Restore, Delete, Virus scan, Updates, Apps..."""
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"time": time.time(), "kind": kind, "summary": summary, **details}) + "\n")


def load():
    """Entries, newest first."""
    try:
        with open(PATH, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except FileNotFoundError:
        return []
    out = []
    for ln in lines[-MAX:]:
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass  # torn last line after a crash
    return out[::-1]


def clear():
    try:
        os.remove(PATH)
    except FileNotFoundError:
        pass
