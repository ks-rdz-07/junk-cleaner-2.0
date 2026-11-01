"""Read-only discovery of junk files. Never deletes anything."""
import glob
import os
import stat
import time

from . import platform_os as osx
from .domain import DAY, RECYCLE_BIN, SAFE_CATEGORIES, JunkItem, classify

SKIP_DIRS = {".git", ".hg", ".svn"}


def _walk_files(top, prune_protected, stop, on_status):
    last = 0.0
    isjunction = getattr(os.path, "isjunction", lambda _: False)
    for dp, dns, fns in os.walk(top, onerror=lambda e: None):
        if stop.is_set():
            return
        dns[:] = [d for d in dns
                  if d.lower() not in SKIP_DIRS
                  and not os.path.islink(full := os.path.join(dp, d)) and not isjunction(full)
                  and not (prune_protected and osx.is_protected(full))]
        if time.time() - last > 0.15:
            on_status(dp)
            last = time.time()
        for f in fns:
            p = os.path.join(dp, f)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                yield p, f, st


WORKTREE_PRUNE = SKIP_DIRS | {"node_modules", "$recycle.bin", "system volume information"}


def find_worktrees(roots, stop, on_status=lambda _: None):
    """Yield every <repo>/.claude/worktrees/<name> folder under roots."""
    isjunction = getattr(os.path, "isjunction", lambda _: False)
    last = 0.0
    for root in roots:
        for dp, dns, _ in os.walk(root, onerror=lambda e: None):
            if stop.is_set():
                return
            if time.time() - last > 0.15:
                on_status(dp)
                last = time.time()
            if os.path.basename(dp).lower() == "worktrees" and os.path.basename(os.path.dirname(dp)) == ".claude":
                yield from (os.path.join(dp, d) for d in dns if not os.path.islink(os.path.join(dp, d)))
                dns[:] = []  # don't look inside worktrees
                continue
            dns[:] = [d for d in dns if d.lower() not in WORKTREE_PRUNE
                      and not os.path.islink(full := os.path.join(dp, d)) and not isjunction(full)
                      and not osx.is_protected(full)]


def _tree_stats(top, stop):
    """(total bytes, newest mtime) of all files under top."""
    size, newest = 0, os.lstat(top).st_mtime
    for dp, dns, fns in os.walk(top, onerror=lambda e: None):
        if stop.is_set():
            break
        for f in fns:
            try:
                st = os.lstat(os.path.join(dp, f))
            except OSError:
                continue
            size += st.st_size
            newest = max(newest, st.st_mtime)
    return size, newest


def scan(opts, stop, on_items, on_status=lambda _: None, batch_size=500):
    """Find junk per ScanOptions. Calls on_items([JunkItem, ...]) in batches; honours stop (threading.Event)."""
    seen, batch, now = set(), [], time.time()

    def emit(path, size, mtime, cat):
        key = os.path.normcase(path)
        if key not in seen:
            seen.add(key)
            batch.append(JunkItem(path, size, mtime, cat, checked=cat in SAFE_CATEGORIES))
            if len(batch) >= batch_size:
                on_items(batch[:])
                batch.clear()

    def fresh(st):
        return opts.skip_recent and now - st.st_mtime < DAY

    if opts.use_system_locations:
        for pattern, cat in osx.system_locations():
            for top in glob.glob(str(pattern)):
                if stop.is_set():
                    break
                if os.path.isfile(top):
                    try:
                        st = os.lstat(top)
                    except OSError:
                        continue
                    if not fresh(st):
                        emit(top, st.st_size, st.st_mtime, cat)
                    continue
                for p, _, st in _walk_files(top, False, stop, on_status):
                    if fresh(st) or (cat == "Temp files" and osx.owned_by_other_user(st)):
                        continue
                    emit(p, st.st_size, st.st_mtime, cat)
        size = osx.recycle_bin_size()
        if size > 0:
            emit(RECYCLE_BIN, size, now, "Trash")

    if opts.worktrees:
        for wt in find_worktrees(osx.all_drives(), stop, on_status):
            size, mtime = _tree_stats(wt, stop)
            if not (opts.skip_recent and now - mtime < DAY):  # recent = an agent may still be using it
                emit(wt, size, mtime, "Agent worktrees")

    for top in opts.folders:
        for p, name, st in _walk_files(top, True, stop, on_status):
            cat = classify(name, st.st_size, opts.large_bytes)
            if cat and not fresh(st):
                emit(p, st.st_size, st.st_mtime, cat)

    if batch:
        on_items(batch)
