"""Everything that differs between Windows and Linux lives here."""
import ctypes
import os
import shutil
import stat
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

WIN = os.name == "nt"
# app data: history, quarantine, downloaded tools
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
                        or os.path.expanduser("~/.local/share"), "JunkCleaner")


# ---------------------------------------------------------------- safety
def _protected_roots():
    if WIN:
        e = os.environ
        roots = [e.get("WINDIR", r"C:\Windows"), e.get("ProgramFiles", r"C:\Program Files"),
                 e.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), e.get("ProgramData", r"C:\ProgramData")]
        roots += [d + p for d in "CDEFGHIJ" for p in (r":\$Recycle.Bin", r":\System Volume Information")]
    else:
        roots = ["/proc", "/sys", "/dev", "/run", "/boot", "/usr", "/bin", "/sbin",
                 "/lib", "/lib32", "/lib64", "/etc", "/snap", "/var/lib"]
    return [os.path.normcase(os.path.abspath(r)) for r in roots]


PROTECTED = _protected_roots()


def is_protected(path):
    """True for OS folders a user-folder scan must never descend into."""
    p = os.path.normcase(os.path.abspath(path))
    return any(p == r or p.startswith(r + os.sep) for r in PROTECTED)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin()) if WIN else os.geteuid() == 0
    except Exception:
        return False


def all_drives():
    """Roots of every mounted local drive."""
    if not WIN:
        return ["/"]
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return [f"{chr(65 + i)}:\\" for i in range(26)
            if mask >> i & 1 and ctypes.windll.kernel32.GetDriveTypeW(f"{chr(65 + i)}:\\") in (2, 3)]  # removable, fixed


def system_info():
    """Basic machine facts: {os, cpu, host, ram: (used, total), drives: [(root, used, total)]}. Never raises."""
    import platform
    info = {"host": platform.node(), "os": platform.platform(terse=True), "cpu": platform.processor(), "ram": None}
    try:
        if WIN:
            import sys
            import winreg
            build = sys.getwindowsversion().build
            info["os"] = f"Windows {'11' if build >= 22000 else platform.release()}  (build {build})"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                info["cpu"] = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()

            class Mem(ctypes.Structure):
                _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                    (n, ctypes.c_ulonglong) for n in ("total", "avail", "tpage", "apage", "tvirt", "avirt", "xvirt")]
            m = Mem(ctypes.sizeof(Mem))
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            info["ram"] = (m.total - m.avail, m.total)
        else:
            rel = dict(ln.rstrip().split("=", 1) for ln in open("/etc/os-release") if "=" in ln)
            info["os"] = rel.get("PRETTY_NAME", info["os"]).strip('"')
            info["cpu"] = next((ln.split(":", 1)[1].strip() for ln in open("/proc/cpuinfo")
                                if ln.startswith("model name")), info["cpu"])
            mem = {ln.split(":")[0]: int(ln.split()[1]) * 1024 for ln in open("/proc/meminfo")}
            info["ram"] = (mem["MemTotal"] - mem["MemAvailable"], mem["MemTotal"])
    except (OSError, KeyError, ValueError):
        pass
    info["cpu"] = f"{info['cpu'] or 'Unknown CPU'}  ·  {os.cpu_count()} threads"
    info["drives"] = []
    for root in all_drives() if WIN else ["/", str(Path.home())]:
        try:
            du = shutil.disk_usage(root)
            info["drives"].append((root, du.used, du.total))
        except OSError:  # empty card reader etc.
            pass
    return info


def owned_by_other_user(st):
    return not WIN and st.st_uid != os.getuid()


# ---------------------------------------------------------- junk locations
def system_locations():
    """(path-or-glob, category) for well-known junk locations of this OS."""
    if WIN:
        la = os.environ.get("LOCALAPPDATA", "")
        win = os.environ.get("WINDIR", r"C:\Windows")
        pd = os.environ.get("ProgramData", r"C:\ProgramData")
        locs = [(os.environ.get("TEMP", ""), "Temp files"), (la + r"\Temp", "Temp files"),
                (win + r"\Temp", "Temp files"), (la + r"\Microsoft\Windows\INetCache", "Cache")]
        for browser in (r"Google\Chrome", r"Microsoft\Edge", r"BraveSoftware\Brave-Browser"):
            for sub in ("Cache", "Code Cache", "GPUCache"):
                locs.append((rf"{la}\{browser}\User Data\*\{sub}", "Cache"))
        locs += [(la + r"\Mozilla\Firefox\Profiles\*\cache2", "Cache"),
                 (la + r"\D3DSCache", "Cache"), (la + r"\NVIDIA\DXCache", "Cache"),
                 (la + r"\pip\Cache", "Cache"), (la + r"\npm-cache\_cacache", "Cache"),
                 (la + r"\Microsoft\Windows\Explorer\thumbcache_*.db", "Cache"),
                 (win + r"\SoftwareDistribution\Download", "Cache"),
                 (la + r"\CrashDumps", "Logs & dumps"), (win + r"\Minidump", "Logs & dumps"),
                 (la + r"\Microsoft\Windows\WER", "Logs & dumps"), (pd + r"\Microsoft\Windows\WER", "Logs & dumps")]
        return [(p, c) for p, c in locs if p and not p.startswith("\\")]
    home = Path.home()
    return [("/tmp", "Temp files"), ("/var/tmp", "Temp files"),  # nosec B108 - folders to clean, not written to
            (os.environ.get("XDG_CACHE_HOME", str(home / ".cache")), "Cache"),
            (str(home / ".thumbnails"), "Cache"), (str(home / ".xsession-errors*"), "Logs & dumps"),
            ("/var/crash", "Logs & dumps"), (str(_trash_dir() / "files"), "Trash")]


# ------------------------------------------------------------ recycle bin
def recycle_bin_size():
    if not WIN:
        return 0

    class Info(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]
    info = Info()
    info.cbSize = ctypes.sizeof(info)
    if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) != 0:
        return 0
    return info.i64Size


def empty_recycle_bin():
    """Returns None on success, else an error string."""
    hr = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4)  # no confirm/progress/sound
    return None if hr == 0 else f"error 0x{hr & 0xFFFFFFFF:08X}"


# ------------------------------------------------------------- deletion
def send_to_trash(paths):
    """Move files to the Recycle Bin / freedesktop Trash. Returns {path: reason} for failures."""
    return _win_recycle(paths) if WIN else _linux_trash_many(paths)


def remove_file(path, from_trash=False):
    if os.path.isdir(path) and not os.path.islink(path):  # whole folder items (agent worktrees)
        shutil.rmtree(path, onerror=lambda f, p, _: (os.chmod(p, stat.S_IWRITE), f(p)))
        return
    try:
        os.remove(path)
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)  # read-only files on Windows
        os.remove(path)
    if from_trash and not WIN:  # drop the matching .trashinfo
        (Path(path).parent.parent / "info" / (Path(path).name + ".trashinfo")).unlink(missing_ok=True)


def _win_recycle(paths):
    from ctypes import wintypes

    class Op(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", ctypes.c_uint), ("pFrom", ctypes.c_wchar_p),
                    ("pTo", ctypes.c_wchar_p), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", ctypes.c_wchar_p)]

    def run(batch):  # FO_DELETE + ALLOWUNDO|NOCONFIRMATION|SILENT|NOERRORUI; ctypes adds the final NUL
        op = Op(None, 3, "\0".join(batch) + "\0", None, 0x40 | 0x10 | 0x4 | 0x400, False, None, None)
        ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))

    run(paths)
    left = [p for p in paths if os.path.lexists(p)]
    for p in left:  # one locked file can abort the whole batch: retry singly
        run([p])
    return {p: "in use or access denied" for p in left if os.path.lexists(p)}


def _trash_dir():
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "Trash"


def _linux_trash_many(paths):
    failed = {}
    for p in paths:
        try:
            _linux_trash(p)
        except OSError as ex:
            failed[p] = ex.strerror or str(ex)
    return failed


def _linux_trash(path):
    base = _trash_dir()
    (base / "files").mkdir(parents=True, exist_ok=True)
    (base / "info").mkdir(parents=True, exist_ok=True)
    name, i = os.path.basename(path), 1
    dest = base / "files" / name
    while dest.exists() or (base / "info" / f"{dest.name}.trashinfo").exists():
        dest, i = base / "files" / f"{name}.{i}", i + 1
    info = base / "info" / f"{dest.name}.trashinfo"
    info.write_text(f"[Trash Info]\nPath={quote(os.path.abspath(path))}\n"
                    f"DeletionDate={datetime.now():%Y-%m-%dT%H:%M:%S}\n")
    try:
        shutil.move(path, dest)
    except OSError:
        info.unlink(missing_ok=True)
        raise


# --------------------------------------------------------------- desktop
def reveal_in_file_manager(path):
    if WIN:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path)])


def enable_dpi_awareness():
    if WIN:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
