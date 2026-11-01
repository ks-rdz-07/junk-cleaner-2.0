"""App quarantine: confirmed junk is moved here instead of deleted, so it can be restored.
Every entry is kept in index.json with its status (Quarantined / Restored / Deleted) - that is the quarantine history."""
import json
import os
import shutil
import threading
import time
import uuid

from . import platform_os as osx

ROOT = os.path.join(osx.DATA_DIR, "quarantine")
RETENTION_DAYS = 30  # quarantined items older than this are deleted at startup
_lock = threading.Lock()


def _index():
    return os.path.join(ROOT, "index.json")


def entries():
    """All entries, newest first: {id, original, size, category, time, status, acted}."""
    try:
        with open(_index(), encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return []


def _save(lst):
    tmp = _index() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(lst, fh)
    os.replace(tmp, _index())  # atomic: a crash never leaves a half-written index


def _payload(qid):
    return os.path.join(ROOT, qid, "payload")  # no extension: a quarantined .exe can't be double-click run


def add(items):
    """Move JunkItems into quarantine. Returns {path: reason} for failures."""
    failed, new = {}, []
    with _lock:
        os.makedirs(ROOT, exist_ok=True)
        for it in items:
            qid = uuid.uuid4().hex
            os.makedirs(os.path.join(ROOT, qid))
            dest = _payload(qid)
            try:
                shutil.move(it.path, dest)
            except OSError as ex:
                if not os.path.lexists(dest):
                    os.rmdir(os.path.join(ROOT, qid))
                    failed[it.path] = ex.strerror or str(ex)
                    continue
                # cross-drive copy finished but the original couldn't be fully removed: keep the copy, never lose data
                failed[it.path] = "copied to quarantine, but the original is in use"
            new.append({"id": qid, "original": it.path, "size": it.size, "category": it.category,
                        "time": time.time(), "status": "Quarantined", "acted": None})
        if new:
            _save(new[::-1] + entries())
    return failed


def _act(ids, status, fn):
    failed = {}
    with _lock:
        lst = entries()
        for e in lst:
            if e["id"] in ids and e["status"] == "Quarantined":
                try:
                    fn(e)
                    e["status"], e["acted"] = status, time.time()
                except OSError as ex:
                    failed[e["id"]] = ex.strerror or str(ex)
        _save(lst)
    return failed


def _restore(e):
    if os.path.lexists(e["original"]):
        raise FileExistsError(0, "something already exists at the original location")
    os.makedirs(os.path.dirname(e["original"]), exist_ok=True)
    shutil.move(_payload(e["id"]), e["original"])
    os.rmdir(os.path.join(ROOT, e["id"]))


def _delete(e):
    if os.path.lexists(_payload(e["id"])):
        osx.remove_file(_payload(e["id"]))
    os.rmdir(os.path.join(ROOT, e["id"]))


def restore(ids):
    """Move entries back to their original paths. Returns {id: reason} for failures."""
    return _act(set(ids), "Restored", _restore)


def delete(ids):
    """Permanently delete quarantined entries. Returns {id: reason} for failures."""
    return _act(set(ids), "Deleted", _delete)


def purge_expired(days=RETENTION_DAYS):
    """Delete quarantined items older than `days`. Returns how many were deleted."""
    cutoff = time.time() - days * 86400
    old = [e["id"] for e in entries() if e["status"] == "Quarantined" and e["time"] < cutoff]
    return len(old) - len(delete(old)) if old else 0
