"""Removes the items the user confirmed. Only ever called after explicit confirmation in the UI."""
from . import platform_os as osx
from . import quarantine
from .domain import CleanResult

CHUNK = 100


def clean(items, use_trash, on_progress=lambda done, total: None, to_quarantine=False):
    """Trash, quarantine or delete `items` (JunkItem list). Returns CleanResult."""
    done, errors, total = [], [], len(items)
    files = [i for i in items if not i.is_recycle_bin]

    for start in range(0, len(files), CHUNK):
        chunk = files[start:start + CHUNK]
        # items already in the Trash are deleted for real
        to_trash = [i for i in chunk if (use_trash or to_quarantine) and i.category != "Trash"]
        failed = {}
        if to_trash:
            failed = quarantine.add(to_trash) if to_quarantine else osx.send_to_trash([i.path for i in to_trash])
        for item in chunk:
            if item in to_trash:
                reason = failed.get(item.path)
            else:
                try:
                    osx.remove_file(item.path, from_trash=item.category == "Trash")
                    reason = None
                except OSError as ex:
                    reason = ex.strerror or str(ex)
            (errors.append((item.path, reason)) if reason else done.append(item))
        on_progress(len(done) + len(errors), total)

    for item in items:
        if item.is_recycle_bin:
            err = osx.empty_recycle_bin()
            (errors.append(("Recycle Bin", err)) if err else done.append(item))
    on_progress(total, total)
    return CleanResult(done, errors)
