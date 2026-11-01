"""Domain model and pure rules - no I/O, no OS calls, no UI."""
import os
import re
from dataclasses import dataclass

MB, DAY = 1024 * 1024, 86400
RECYCLE_BIN = "::RECYCLE_BIN::"  # pseudo path: the whole Windows Recycle Bin

CATEGORIES = ["Temp files", "Cache", "Logs & dumps", "System junk",
              "Backups & leftovers", "Trash", "Empty files", "Large files", "Agent worktrees"]
SAFE_CATEGORIES = {"Temp files", "Cache", "Logs & dumps", "System junk", "Trash"}  # pre-checked after a scan

TEMP_EXT = {".tmp", ".temp"}
LOG_EXT = {".log", ".dmp", ".mdmp", ".hdmp"}
BAK_EXT = {".bak", ".old", ".orig", ".swp", ".swo", ".chk", ".gid"}
SYS_NAMES = {"thumbs.db", "ehthumbs.db", ".ds_store"}
EMPTY_KEEP = {"__init__.py", "py.typed"}  # empty on purpose


@dataclass(slots=True)
class JunkItem:
    path: str
    size: int
    mtime: float
    category: str
    checked: bool = False

    @property
    def is_recycle_bin(self):
        return self.path == RECYCLE_BIN

    @property
    def name(self):
        return "Recycle Bin (all drives)" if self.is_recycle_bin else os.path.basename(self.path)

    @property
    def location(self):
        return "Windows Recycle Bin" if self.is_recycle_bin else os.path.dirname(self.path)


@dataclass
class ScanOptions:
    use_system_locations: bool = True
    folders: tuple = ()
    large_bytes: int = 500 * MB
    skip_recent: bool = True  # ignore files changed in the last 24 h (likely in use)
    worktrees: bool = False  # Claude agent worktrees (<repo>/.claude/worktrees/*) on all drives


@dataclass
class CleanResult:
    done: list
    errors: list  # [(path, reason)]

    @property
    def freed(self):
        return sum(i.size for i in self.done)


def classify(name, size, large_bytes):
    """Category for a file found in a user-chosen folder, or None if it is not junk."""
    n = name.lower()
    ext = os.path.splitext(n)[1]
    if n in SYS_NAMES or n.startswith("._"):
        return "System junk"
    if ext in TEMP_EXT or n.startswith("~$") or n.startswith(".~lock"):
        return "Temp files"
    if ext in LOG_EXT or re.search(r"\.log\.\d+(\.gz)?$", n):
        return "Logs & dumps"
    if ext in BAK_EXT or n.endswith("~"):
        return "Backups & leftovers"
    if size == 0 and not n.startswith(".") and n not in EMPTY_KEEP:
        return "Empty files"
    if large_bytes and size >= large_bytes:
        return "Large files"
    return None


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def freed_bytes(history, quarantined):
    """Bytes that really left the disk: cleanups not moved to quarantine, plus quarantined items since deleted or expired.
    history: Clean entries carry mode bin|quarantine|delete (entries logged before modes existed count as before)."""
    cleaned = sum(h.get("bytes", 0) for h in history if h["kind"] == "Clean" and h.get("mode") != "quarantine")
    return cleaned + sum(e["size"] for e in quarantined if e["status"] == "Deleted")
