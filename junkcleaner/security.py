"""Security checks built on tools Windows already trusts: Microsoft Safety Scanner, Windows Update, winget.
No UI here. Windows only."""
import os
import re
import subprocess
import time
import urllib.request

from .platform_os import DATA_DIR

WIN = os.name == "nt"
NO_WINDOW = 0x08000000 if WIN else 0  # CREATE_NO_WINDOW: no console flash from the GUI app
MSERT_URL = "https://go.microsoft.com/fwlink/?LinkId=212732"  # Microsoft Safety Scanner, x64
MSERT_MAX_AGE = 10 * 86400  # Microsoft: a download expires after 10 days
CACHE = DATA_DIR
MSERT_LOG = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "debug", "msert.log")


def _run(args, timeout=None):
    out = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=timeout, creationflags=NO_WINDOW)
    return out.returncode, out.stdout, out.stderr


def _ps(script, timeout=None):
    code, out, err = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                           "[Console]::OutputEncoding=[Text.Encoding]::UTF8;" + script], timeout)
    if code:
        raise RuntimeError(err.strip().splitlines()[0] if err.strip() else f"PowerShell exit code {code}")
    return out


def _q(s):  # PowerShell single-quoted literal
    return "'" + s.replace("'", "''") + "'"


# ------------------------------------------------------------- virus scan
def ensure_safety_scanner(on_status=lambda text, pct=None: None):
    """Path to a current, Microsoft-signed msert.exe; downloads it when missing or expired (pct = download %)."""
    exe = os.path.join(CACHE, "msert.exe")
    if not os.path.exists(exe) or time.time() - os.path.getmtime(exe) > MSERT_MAX_AGE:
        os.makedirs(CACHE, exist_ok=True)
        part = exe + ".part"

        def hook(blocks, bs, total):
            if total > 0:
                pct = min(100, blocks * bs * 100 // total)
                on_status(f"Downloading Microsoft Safety Scanner… {pct}%", pct)
        urllib.request.urlretrieve(MSERT_URL, part, hook)  # nosec B310 - fixed https Microsoft URL, signature checked below
        os.replace(part, exe)
    # it will run elevated: refuse anything not validly signed by Microsoft
    sig = _ps(f"$s=Get-AuthenticodeSignature -LiteralPath {_q(exe)}; \"$($s.Status)|$($s.SignerCertificate.Subject)\"")
    status, _, subject = sig.strip().partition("|")
    if status != "Valid" or "O=Microsoft Corporation" not in subject:
        os.remove(exe)
        raise RuntimeError(f"Safety Scanner signature check failed ({status}); the file was deleted.")
    return exe


def run_safety_scanner(exe, full):
    """Scan and remove threats. Blocks until done (quick ≈ minutes, full ≈ hours). Asks for UAC."""
    args = "'/Q','/F'" if full else "'/Q'"  # /Q quiet; without /N it removes what it finds
    _ps(f"$p=Start-Process -FilePath {_q(exe)} -ArgumentList {args} -Verb RunAs -Wait -PassThru; $p.ExitCode")
    return parse_msert_log(read_msert_log())


def read_msert_log():
    with open(MSERT_LOG, "rb") as fh:
        raw = fh.read()
    return raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", "replace")


def parse_msert_log(text):
    """(threat lines, file paths, summary lines) of the last run in msert.log."""
    run = text[text.rfind("Microsoft Safety Scanner v"):]
    lines = [ln.strip() for ln in run.splitlines()]
    threats = [ln.split(":", 1)[1].strip() for ln in lines if ln.startswith("Threat Detected:")]
    files = [ln.split()[0][len("file://"):] for ln in lines if ln.startswith("file://")]
    summary, inside = [], False
    for ln in lines:
        if ln.startswith("Results Summary"):
            inside = True
        elif inside and ln.startswith("Microsoft Safety Scanner Finished"):
            break
        elif inside and ln and not ln.startswith("-"):
            summary.append(ln)
    return threats, files, summary


# ------------------------------------------------- missing Windows updates
def missing_windows_updates():
    """[{Title, KB, Severity, CVEs}] for software updates Windows Update has not installed."""
    import json
    out = _ps("$r=(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()"
              ".Search(\"IsInstalled=0 and IsHidden=0 and Type='Software'\");"
              "$l=foreach($u in $r.Updates){[pscustomobject]@{Title=$u.Title;KB=(@($u.KBArticleIDs)-join ',');"
              "Severity=[string]$u.MsrcSeverity;CVEs=(@($u.CveIDs)-join ',')}};"
              "ConvertTo-Json -InputObject @($l) -Compress", timeout=900)
    return json.loads(out or "[]")


# ------------------------------------------------------------ outdated apps
def outdated_apps():
    code, out, err = _run(["winget", "upgrade", "--accept-source-agreements", "--disable-interactivity"], 600)
    return parse_winget_table(out)


def parse_winget_table(text):
    """Rows of `winget upgrade` output as dicts: name, id, version, available, source."""
    lines = [ln.split("\r")[-1].rstrip() for ln in text.splitlines()]  # drop spinner redraws
    head = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith("Name") and " Id " in ln
                 and "Available" in ln), None)
    if head is None:
        return []
    h = lines[head]
    start = len(h) - len(h.lstrip())
    cols = [start] + [h.index(c) for c in (" Id ", " Version ", " Available ", " Source")]
    cols = [cols[0]] + [c + 1 for c in cols[1:]]
    rows = []
    for ln in lines[head + 2:]:
        if len(ln) <= cols[3] or not ln[cols[4]:].strip():
            break  # blank line or "N upgrades available." ends the table
        f = [ln[a:b].strip() for a, b in zip(cols, cols[1:] + [None])]
        rows.append(dict(zip(("name", "id", "version", "available", "source"), f)))
    return rows


UNITS = {"B": 1, "KB": 1 << 10, "MB": 1 << 20, "GB": 1 << 30}


def parse_winget_progress(text):
    """(percent or None, stage or None) from one redraw of winget's progress output."""
    m = re.search(r"([\d.]+)\s*(B|KB|MB|GB)\s*/\s*([\d.]+)\s*(B|KB|MB|GB)", text)
    if m:
        done, total = float(m[1]) * UNITS[m[2]], float(m[3]) * UNITS[m[4]]
        return (min(100, int(done * 100 / total)) if total else None), f"Downloading {m[1]} {m[2]} / {m[3]} {m[4]}"
    m = re.search(r"(\d{1,3})\s*%", text)
    if m:
        return min(100, int(m[1])), None
    t = text.lower()
    if "verified installer hash" in t or "starting package install" in t:
        return None, "Installing…"
    if "downloading" in t:
        return None, "Downloading…"
    return None, None


def upgrade_app(app_id, on_progress=lambda pct, stage: None, timeout=3600):
    """Upgrade one app with winget. Never raises: returns (ok, message). on_progress gets live download %/stage."""
    import threading
    args = ["winget", "upgrade", "--id", app_id, "--exact", "--silent", "--accept-package-agreements",
            "--accept-source-agreements", "--disable-interactivity"]
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    except OSError as ex:
        return False, ex.strerror or str(ex)
    lines = []

    def read():  # winget redraws its progress bar with CR, so read raw chunks rather than lines
        buf = ""
        while chunk := proc.stdout.read1(4096):
            buf += chunk.decode("utf-8", "replace")
            *parts, buf = re.split(r"[\r\n]", buf)
            for part in parts:
                if part.strip():
                    lines.append(part.strip())
                    pct, stage = parse_winget_progress(part)
                    if pct is not None or stage:
                        on_progress(pct, stage)
        if buf.strip():
            lines.append(buf.strip())
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        code = proc.wait(timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return False, f"timed out after {timeout // 60} min (its installer may still be finishing in the background)"
    reader.join(5)
    if code & 0xFFFFFFFF in BUSY_CODES:
        return False, "another installation is in progress"
    return code == 0, summary_line(lines, code)


# Windows Installer runs one install at a time; a parallel update can hit this and must be retried later
BUSY_CODES = {1618, 0x8A15010B}  # ERROR_INSTALL_ALREADY_RUNNING, winget "installer is busy"


def summary_line(lines, code):
    """Last real message from winget output, skipping progress-bar redraws and spinner frames."""
    noise = re.compile(r"[█▒]|^[\d.]+\s*(B|KB|MB|GB)\s*/|^\d+\s*%$|^[-\\|/]$")
    text = [ln for ln in lines if not noise.search(ln)]
    return text[-1] if text else f"exit code {code}"


def is_busy_failure(msg):
    m = msg.lower()
    return "another installation" in m or "1618" in m or "installer is busy" in m


# ------------------------------------------------------ protection status
def decode_av_state(state):
    """(enabled, up_to_date) from SecurityCenter2 productState, e.g. 0x061100 -> (True, True)."""
    return bool(state >> 12 & 1), state & 0xF0 == 0


def protection_status():
    """{'antivirus': [{name, enabled, up_to_date}], 'firewall': [{name, enabled}]} - works for McAfee, Defender..."""
    import json
    out = _ps("$a=@(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct|"
              "%{[pscustomobject]@{Name=$_.displayName;State=[int]$_.productState}});"
              "$f=@(Get-NetFirewallProfile|%{[pscustomobject]@{Name=$_.Name;Enabled=[bool]$_.Enabled}});"
              "ConvertTo-Json -InputObject @{A=$a;F=$f} -Compress -Depth 3", timeout=90)
    d = json.loads(out)
    av = [{"name": a["Name"], **dict(zip(("enabled", "up_to_date"), decode_av_state(a["State"])))}
          for a in d.get("A") or []]
    return {"antivirus": av, "firewall": [{"name": f["Name"], "enabled": f["Enabled"]} for f in d.get("F") or []]}


# ------------------------------------------------ Defender protection history
THREAT_STATUS = {0: "Unknown", 1: "Detected", 2: "Cleaned", 3: "Quarantined", 4: "Removed", 5: "Allowed",
                 6: "Blocked", 102: "Quarantine failed", 103: "Remove failed", 104: "Allow failed",
                 105: "Abandoned", 107: "Block failed"}


def defender_history():
    """[{time, threat, severity, status, files}] from Microsoft Defender's own detection history."""
    import json
    out = _ps("$n=@{};Get-MpThreat|%{$n[[string]$_.ThreatID]=@($_.ThreatName,[int]$_.SeverityID)};"
              "$l=foreach($d in Get-MpThreatDetection){$t=$n[[string]$d.ThreatID];[pscustomobject]@{"
              "Time=$d.InitialDetectionTime.ToString('yyyy-MM-dd HH:mm');Threat=$t[0];Sev=$t[1];"
              "Status=[int]$d.ThreatStatusID;Files=(@($d.Resources)-join ' | ')}};"
              "ConvertTo-Json -InputObject @($l) -Compress", timeout=120)
    sev = {1: "Low", 2: "Moderate", 4: "High", 5: "Severe"}
    return [{"time": r["Time"], "threat": r["Threat"] or "Unknown", "severity": sev.get(r["Sev"], "—"),
             "status": THREAT_STATUS.get(r["Status"], str(r["Status"])), "files": r["Files"]}
            for r in json.loads(out or "[]")]
