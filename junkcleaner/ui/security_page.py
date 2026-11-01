"""Security page: virus scan, Defender protection history, missing Windows updates, outdated apps."""
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QComboBox, QMessageBox, QProgressBar, QTabWidget, QVBoxLayout, QWidget

from .. import history
from ..domain import fmt_size
from .. import security as sec
from . import common as c


class SecurityPage(QWidget):
    activity = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.busy, self.buttons = False, []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(12)
        lay.addWidget(c.label("Security", "h1"))
        lay.addWidget(c.label("On-demand checks that work next to your antivirus (McAfee, Defender, …). "
                              "Nothing here replaces real-time protection.", "muted", wrap=True))
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        self.progress = c.Progress()
        lay.addWidget(self.progress)
        self._virus_tab()
        self._defender_tab()
        self._updates_tab()
        self._apps_tab()

    # ------------------------------------------------------------ helpers
    def _tab(self, title, text, *buttons):
        w = QWidget()
        w.setObjectName("page")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 14, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(c.label(text, "muted", wrap=True))
        self.buttons += buttons
        lay.addWidget(c.row(*buttons, stretch_at=len(buttons)))
        self.tabs.addTab(w, title)
        return lay

    def _work(self, msg, fn, done, kind, fail=None):
        """fn() off the UI thread, done(result) back on it. One job at a time. fail(error) runs on failure."""
        if self.busy:
            return
        self.busy = True
        for b in self.buttons:
            b.setEnabled(False)
        self.progress.busy(msg)

        def finish(ok, value):
            self.busy = False
            for b in self.buttons:
                b.setEnabled(True)
            if ok:
                done(value)
            else:
                if fail:
                    fail(value)
                self.progress.done(f"Failed: {value}")
                history.log(kind, f"Failed: {value}")
                self.activity.emit()
                c.notify(f"{kind} failed", str(value))
                QMessageBox.critical(self, "Security", str(value))
        c.run_bg(fn, lambda r: finish(True, r), lambda ex: finish(False, ex))

    def _say(self, text, pct=None):  # called from worker threads
        if pct is None:
            c.ui(self.progress.busy, text)
        else:
            c.ui(self.progress.set, pct, 100, text)

    def _done(self, kind, msg):
        self.progress.done(msg)
        history.log(kind, msg)
        self.activity.emit()
        c.notify(f"{kind} finished", msg)

    # ------------------------------------------------------------ virus scan
    def _virus_tab(self):
        lay = self._tab("Virus scan", "Microsoft Safety Scanner: Microsoft's free on-demand scanner. It removes "
                        "threats it finds. First use downloads it (about 200 MB, valid 10 days) and verifies "
                        "Microsoft's signature before running it.",
                        c.button("Quick scan", lambda: self.virus_scan(False), "primary"),
                        c.button("Full scan  (can take hours)", lambda: self.virus_scan(True)))
        card, cl = c.card(margins=(18, 14, 18, 14), spacing=6)
        self.vsteps = c.label(wrap=True)
        self.vsteps.setTextFormat(Qt.RichText)
        self.vactivity = c.label("", wrap=True)
        self.vactivity.setStyleSheet("font-size: 11pt; font-weight: 600;")
        self.vhint = c.label("", "muted", wrap=True)
        for w in (self.vsteps, self.vactivity, self.vhint):
            cl.addWidget(w)
        lay.addWidget(card)
        self.vtable = c.table(["Result", "Detail"])
        lay.addWidget(self.vtable, 1)
        self.vtimer = QTimer(self, interval=1000, timeout=self._poll_scanner)
        self._scan_started, self._scan_seen = 0.0, False
        self._scan_state(-1)

    VSTEPS = ("Download and verify Microsoft Safety Scanner", "Administrator approval (Windows asks)",
              "Scanning", "Reading results")

    def _scan_state(self, step, failed=False, note=""):
        """Render the checklist: steps before `step` done, `step` active (or failed), the rest pending.
        step -1 = idle, len(VSTEPS) = all done."""
        from .theme import C
        self.vstep = step
        rows = []
        for i, name in enumerate(self.VSTEPS):
            if step >= 0 and (i < step or step >= len(self.VSTEPS)):
                icon, color = "✓", C["ok"]
            elif i == step:
                icon, color = ("✗", C["danger"]) if failed else ("●", C["accent"])
            else:
                icon, color = "○", C["muted"]
            weight = "600" if i == step else "400"
            rows.append(f'<span style="color:{color}">{icon}</span>&nbsp;&nbsp;'
                        f'<span style="font-weight:{weight}">{name}</span>')
        self.vsteps.setText("<br>".join(rows))
        if note:
            self.vactivity.setText(note)
        if step < 0:
            self.vactivity.setText("Press Quick scan to start.")
            self.vhint.setText("Quick scans usually take 5–20 minutes; full scans can take hours. Microsoft's scanner "
                               "reports results only at the end, so its live disk activity is shown while it works.")

    def _poll_scanner(self):
        act = sec.scanner_activity()
        if not act:
            return
        running, read, ops = act
        if running and self.vstep in (1, 2):
            if self.vstep == 1:
                self._scan_state(2)
            self._scan_seen = True
            mins, secs = divmod(int(time.time() - self._scan_started), 60)
            self.vactivity.setText(f"Scanning…  {fmt_size(read)} read from disk  ·  {ops:,} read operations  ·  "
                                   f"{mins}:{secs:02d} elapsed")
            self.vhint.setText("You can keep using the PC. You'll get a notification when the scan finishes.")
        elif not running and self.vstep == 2 and self._scan_seen:
            self._scan_state(3, note="Scanner finished. Reading its log…")

    def virus_scan(self, full):
        kind = "Full" if full else "Quick"
        if not c.confirm(self, "Virus scan", f"Run a {kind.lower()} scan?\n\nThreats found will be removed "
                                             "automatically. Windows will ask for administrator approval."):
            return
        started = self._scan_started = time.time()
        self._scan_seen = False
        self.vtable.setRowCount(0)
        self._scan_state(0, note="Checking for a current, Microsoft-signed scanner…")

        def say(text, pct=None):  # worker thread: download progress
            self._say(text, pct)
            c.ui(self.vactivity.setText, text)

        def job():
            exe = sec.ensure_safety_scanner(say)
            c.ui(self._scan_state, 1, False, "Waiting for you to approve the Windows administrator prompt…")
            c.ui(self.vtimer.start)
            self._say(f"{kind} scan running - you can keep using the PC")
            return sec.run_safety_scanner(exe, full)

        def done(res):
            self.vtimer.stop()
            threats, files, summary = res
            c.fill(self.vtable, [("Threat", t) for t in threats] + [("File", f) for f in files]
                   + [("Summary", s) for s in summary])
            mins = round((time.time() - started) / 60)
            took = f"{mins} min" if mins else "under a minute"
            result = f"{len(threats)} threat(s) found and removed" if threats else "no threats found"
            self._scan_state(len(self.VSTEPS), note=f"{kind} scan finished in {took}: {result}.")
            self.vhint.setText("Details are in the table below and in History.")
            self._done("Virus scan", f"{kind} scan, {took}: {result}")

        def fail(err):
            self.vtimer.stop()
            self._scan_state(max(self.vstep, 0), failed=True, note=f"Stopped: {err}")
        self._work("Preparing Microsoft Safety Scanner…", job, done, "Virus scan", fail)

    # ------------------------------------------------------- defender history
    def _defender_tab(self):
        lay = self._tab("Protection history", "Threats Microsoft Defender detected on this PC and what it did "
                        "(quarantined, removed, allowed). If another antivirus such as McAfee is active, Defender is "
                        "passive and its history is empty - open that product to see its own quarantine.",
                        c.button("Load history", self._load_defender, "primary"),
                        c.button("Open Windows Security", lambda: webbrowser.open("windowsdefender://threat/")))
        self.dtable = c.table(["Detected", "Threat", "Severity", "Status", "Affected items"])
        lay.addWidget(self.dtable, 1)

    def _load_defender(self):
        def done(rows):
            c.fill(self.dtable, [(r["time"], r["threat"], r["severity"], r["status"], r["files"]) for r in rows])
            self.progress.done(f"Defender history: {len(rows)} detection(s)." if rows
                               else "Defender history is empty.")
        self._work("Reading Microsoft Defender history…", sec.defender_history, done, "Protection history")

    # ---------------------------------------------------- windows updates/CVE
    def _updates_tab(self):
        lay = self._tab("Windows updates", "Updates Windows Update has not installed yet, with the publicly "
                        "reported vulnerabilities (CVE) they fix. Double-click a row to read the CVE.",
                        c.button("Check now", self.check_updates, "primary"),
                        c.button("Open Windows Update", lambda: webbrowser.open("ms-settings:windowsupdate")))
        self.utable = c.table(["Update", "KB", "Severity", "CVEs"], stretch=0)
        self.utable.doubleClicked.connect(self._open_cve)
        lay.addWidget(self.utable, 1)

    def check_updates(self):
        def done(rows):
            c.fill(self.utable, [(u["Title"], u["KB"], u["Severity"] or "—", u["CVEs"] or "—") for u in rows])
            cves = sum(len(u["CVEs"].split(",")) for u in rows if u["CVEs"])
            self._done("Updates", f"{len(rows)} missing update(s) fixing {cves} public CVE(s)" if rows
                       else "Windows is up to date")
        self._work("Asking Windows Update… (can take a few minutes)", sec.missing_windows_updates, done, "Updates")

    def _open_cve(self, idx):
        cves = self.utable.item(idx.row(), 3).text()
        if cves.startswith("CVE-"):
            webbrowser.open(f"https://www.cve.org/CVERecord?id={cves.split(',')[0]}")

    # ----------------------------------------------------------- outdated apps
    def _apps_tab(self):
        lay = self._tab("Outdated apps", "Installed apps with a newer version available (winget). Old versions "
                        "are the most common way known vulnerabilities reach a PC. Tick apps and press Update selected.",
                        c.button("Check now", self._check_apps, "primary"),
                        c.button("Select all", lambda: c.set_all_checked(self.atable, True)),
                        c.button("Select none", lambda: c.set_all_checked(self.atable, False)),
                        c.button("Update selected", lambda: self._update(c.checked_data(self.atable))),
                        c.button("Update all", lambda: self._update(
                            [self.atable.item(r, 0).data(Qt.UserRole) for r in range(self.atable.rowCount())])))
        self.parallel = QComboBox()
        self.parallel.addItems(["One at a time", "2 at once", "3 at once", "4 at once"])
        self.parallel.setToolTip("Downloads run in parallel. Windows installs one MSI at a time, so an update that "
                                 "collides is retried on its own at the end.")
        self.buttons.append(self.parallel)
        lay.addWidget(c.row(c.label("Parallel updates", "muted"), self.parallel, stretch_at=2))
        self.atable = c.table(["App", "Id", "Installed", "Available", "Source", "Progress / result"], stretch=0)
        lay.addWidget(self.atable, 1)

    def _check_apps(self):
        def done(rows):
            c.fill(self.atable, [(a["name"], a["id"], a["version"], a["available"], a["source"], "") for a in rows],
                   data=[a["id"] for a in rows], checkable=True)
            self.atable.setColumnWidth(5, 320)
            self.progress.done(f"{len(rows)} app(s) have updates." if rows else "All apps are up to date.")
        self._work("Checking installed apps with winget…", sec.outdated_apps, done, "Apps")

    def _row_progress(self, row, pct, stage):
        bar = self.atable.cellWidget(row, 5)
        if bar is None:
            self.atable.item(row, 5).setText("")
            bar = QProgressBar(objectName="cell", maximum=100, value=0)
            self.atable.setCellWidget(row, 5, bar)
        if pct is not None:
            bar.setValue(pct)
        if stage:
            bar.setProperty("stage", stage)
        bar.setFormat(f"{bar.property('stage') or 'Updating'}  ·  %p%")

    def _row_result(self, row, ok, msg):
        self.atable.removeCellWidget(row, 5)
        self.atable.item(row, 5).setText(("✓ " if ok else "✗ ") + msg)
        self.atable.item(row, 5).setToolTip(msg)

    def _update(self, ids):
        if not ids:
            QMessageBox.information(self, "Update", "Press Check now and tick the apps to update.")
            return
        if not c.confirm(self, "Update apps", f"Update {len(ids)} app(s)? Close them first; some installers may "
                                              "ask for permission."):
            return
        workers = self.parallel.currentIndex() + 1
        self.atable.setSortingEnabled(False)  # rows must stay put while their progress bars update
        rows = {self.atable.item(r, 0).data(Qt.UserRole): r for r in range(self.atable.rowCount())}
        for i in ids:
            self._row_result(rows[i], True, "")
            self.atable.item(rows[i], 5).setText("Queued")
        frac, results, last = {i: 0.0 for i in ids}, {}, {}

        def overall():
            done_n = len(results)
            pct = int(sum(frac.values()) * 100 / len(ids))
            running = len(ids) - done_n
            self.progress.set(pct, 100, f"Updating apps: {done_n} of {len(ids)} done, {running} left  ·  {pct}% overall")

        def one(i, label="Starting…"):
            c.ui(self._row_progress, rows[i], 0, label)

            def prog(pct, stage):  # from winget's reader thread; only forward changes
                if last.get(i) == (pct, stage):
                    return
                last[i] = (pct, stage)
                if pct is not None:
                    frac[i] = pct / 100 * 0.9  # the last 10% is the install itself
                c.ui(self._row_progress, rows[i], pct, stage)
                c.ui(overall)
            results[i] = sec.upgrade_app(i, prog)
            frac[i] = 1.0
            if workers > 1 and label == "Starting…" and not results[i][0] and sec.is_busy_failure(results[i][1]):
                c.ui(self._row_result, rows[i], True, "")
                c.ui(lambda r=rows[i]: self.atable.item(r, 5).setText("Waiting to retry on its own…"))
            else:
                c.ui(self._row_result, rows[i], *results[i])
            c.ui(overall)

        def job():
            with ThreadPoolExecutor(workers) as pool:
                list(pool.map(one, ids))
            for i in [i for i, (ok, msg) in results.items() if not ok and sec.is_busy_failure(msg)]:
                del results[i]
                frac[i] = 0.0
                one(i, "Retrying on its own…")
            return results

        def done(res):
            self.atable.setSortingEnabled(True)
            ok = sum(good for good, _ in res.values())
            failed = [i for i, (good, _) in res.items() if not good]
            self._done("Apps", f"Updated {ok} of {len(res)} app(s)" + (f"; failed: {', '.join(failed)}" if failed else ""))
        self._work("Updating…", job, done, "Apps")
