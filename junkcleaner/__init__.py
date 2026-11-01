"""Junk Cleaner - find, review and remove junk files on Windows and Linux.

Layers (dependencies point inward only):
    domain.py       pure model + rules (no I/O)
    platform_os.py  Windows/Linux specifics (paths, Recycle Bin/Trash, admin)
    scanner.py      read-only discovery      -> domain, platform_os
    cleaner.py      deletion of confirmed items -> domain, platform_os
    history.py      activity log (JSON lines)
    quarantine.py   restorable store for cleaned items + its history
    security.py     AV/firewall status, Defender history, Safety Scanner, updates, winget
    ui/             PySide6 front end        -> everything above
"""
__version__ = "2.0.1"
