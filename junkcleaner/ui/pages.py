"""Dashboard, Quarantine and History pages."""
import csv
import os
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QMessageBox, QProgressBar,
                               QVBoxLayout, QWidget)

from .. import history, quarantine
from .. import platform_os as osx
from .. import security as sec
from ..domain import fmt_size, freed_bytes
from . import common as c
from .theme import C


def when(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "—"


def _page(title, subtitle):
    w = QWidget()
    w.setObjectName("page")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(24, 20, 24, 16)
    lay.setSpacing(12)
    lay.addWidget(c.label(title, "h1"))
    lay.addWidget(c.label(subtitle, "muted", wrap=True))
    return w, lay


# =================================================================== dashboard
class DashboardPage(QWidget):
    go = Signal(str)  # "scan" | "virus" | "updates"

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(14)
        lay.addWidget(c.label("Overview", "h1"))

        self.banner = QFrame(objectName="banner")
        self.banner.setStyleSheet(f"QFrame#banner {{ background: {C['accent']}; }}")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(22, 18, 22, 18)
        text = QVBoxLayout()
        self.banner_title = c.label("Checking protection…", "h2")
        self.banner_title.setStyleSheet("font-size: 15pt; color: white; background: transparent;")
        self.banner_text = c.label("", wrap=True)
        self.banner_text.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent;")
        text.addWidget(self.banner_title)
        text.addWidget(self.banner_text)
        bl.addLayout(text, 1)
        for t, k, kind in (("Scan for junk", "scan", None), ("Quick virus scan", "virus", None),
                           ("Check updates", "updates", None)):
            b = c.button(t, lambda k=k: self.go.emit(k), kind)
            b.setStyleSheet("QPushButton { background: rgba(255,255,255,0.16); border: 1px solid "
                            "rgba(255,255,255,0.35); color: white; font-weight: 600; }"
                            "QPushButton:hover { background: rgba(255,255,255,0.28); }")
            bl.addWidget(b)
        lay.addWidget(self.banner)

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.t_av = c.StatCard("Antivirus", "#2f81f7")
        self.t_fw = c.StatCard("Firewall", "#8b5cf6")
        self.t_junk = c.StatCard("Last junk scan", "#d29922")
        self.t_freed = c.StatCard("Freed all time", "#3fb950")
        self.t_q = c.StatCard("Quarantine", "#f85149")
        for t in (self.t_av, self.t_fw, self.t_junk, self.t_freed, self.t_q):
            tiles.addWidget(t, 1)
        lay.addLayout(tiles)

        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        sysbox, self.sys_lay = c.card(QGridLayout, margins=(18, 14, 18, 14))
        sysbox.setMinimumWidth(420)
        bottom.addWidget(sysbox)
        recent, rl = c.card()
        rl.addWidget(c.label("RECENT ACTIVITY", "section"))
        self.recent = c.table(["Time", "Activity", "Summary"])
        self.recent.setFrameShape(QFrame.NoFrame)
        self.recent.setStyleSheet("QTableView { border: none; }")
        rl.addWidget(self.recent, 1)
        bottom.addWidget(recent, 1)
        lay.addLayout(bottom, 1)
        self._av = None
        self.refresh()
        self.refresh_protection()

    def refresh_protection(self):
        if not osx.WIN:
            self._av = {"antivirus": [], "firewall": []}
            self._paint_banner()
            return
        c.run_bg(sec.protection_status, self._set_av, lambda ex: self._set_av({"error": str(ex)}))

    def _set_av(self, st):
        self._av = st
        if "error" in st:
            self.t_av.set("Unknown", st["error"][:80])
            self.t_fw.set("Unknown")
        else:
            on = [a for a in st["antivirus"] if a["enabled"]]
            self.t_av.set(", ".join(a["name"] for a in on) or "Off",
                          "Up to date" if on and all(a["up_to_date"] for a in on) else
                          ("Definitions out of date" if on else "No active antivirus"))
            fw = st["firewall"]
            off = [f["name"] for f in fw if not f["enabled"]]
            self.t_fw.set("On" if fw and not off else ("Off" if fw else "—"),
                          f"Off for: {', '.join(off)}" if off else f"{len(fw)} profiles on")
        self._paint_banner()

    def _paint_banner(self):
        st = self._av or {}
        issues = []
        if "error" not in st and osx.WIN:
            on = [a for a in st.get("antivirus", []) if a["enabled"]]
            if not on:
                issues.append("no active antivirus")
            elif not all(a["up_to_date"] for a in on):
                issues.append("antivirus definitions are out of date")
            if any(not f["enabled"] for f in st.get("firewall", [])):
                issues.append("the firewall is off for a network profile")
        scans = [h for h in history.load() if h["kind"] == "Virus scan" and not h["summary"].startswith("Failed")]
        if not scans:
            issues.append("no on-demand virus scan yet")
        ok = not issues
        color = C["ok"] if ok else C["warn"]
        self.banner.setStyleSheet(f"QFrame#banner {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
                                  f"stop:0 {color}, stop:1 {C['accent']}); }}")
        self.banner_title.setText("✓  Your PC looks protected" if ok else "!  Attention recommended")
        last = f"Last virus scan: {when(scans[0]['time'])}." if scans else ""
        self.banner_text.setText(("Antivirus and firewall are on. " + last) if ok
                                 else "Found: " + "; ".join(issues) + ". " + last)

    def refresh(self):
        """Re-read history, quarantine and system facts (cheap; called after any activity)."""
        hist = history.load()
        scan = next((h for h in hist if h["kind"] == "Scan"), None)
        self.t_junk.set(fmt_size(scan.get("bytes", 0)) if scan else "Never",
                        f"{scan.get('items', 0):,} items · {when(scan['time'])}" if scan else "Press Scan for junk")
        self.t_freed.set(fmt_size(freed_bytes(hist, quarantine.entries())),
                         f"{sum(1 for h in hist if h['kind'] == 'Clean')} cleanup(s)")
        q = [e for e in quarantine.entries() if e["status"] == "Quarantined"]
        self.t_q.set(f"{len(q):,} items", fmt_size(sum(e["size"] for e in q)))
        c.fill(self.recent, [((when(h["time"]), h["time"]), h["kind"], h["summary"]) for h in hist[:30]])
        self._fill_sys()
        if self._av is not None:
            self._paint_banner()

    def _fill_sys(self):
        g = self.sys_lay
        while g.count():
            old = g.takeAt(0).widget()
            old.setParent(None)  # hide now; deleteLater alone leaves it painted until the next event loop pass
            old.deleteLater()
        info = osx.system_info()
        g.addWidget(c.label("THIS PC", "section"), 0, 0, 1, 2)
        rows = [("Device", info["host"]), ("OS", info["os"]), ("CPU", info["cpu"])]
        if info["ram"]:
            rows.append(("RAM", f"{fmt_size(info['ram'][0])} of {fmt_size(info['ram'][1])} in use"))
        r = 1
        for k, v in rows:
            g.addWidget(c.label(k, "muted"), r, 0, Qt.AlignTop)
            g.addWidget(c.label(v, wrap=True), r, 1)
            r += 1
        for root, used, total in info["drives"]:
            g.addWidget(c.label(root.rstrip("\\/") or "/", "muted"), r, 0)
            g.addWidget(c.label(f"{fmt_size(total - used)} free of {fmt_size(total)}"), r, 1)
            bar = QProgressBar(maximum=1000, value=int(used * 1000 / total))
            if used / total > 0.9:
                bar.setObjectName("danger")
            g.addWidget(bar, r + 1, 1)
            r += 2
        g.setRowStretch(r, 1)
        g.setColumnStretch(1, 1)


# ================================================================== quarantine
class QuarantinePage(QWidget):
    activity = Signal()

    def __init__(self):
        super().__init__()
        w, lay = _page("Quarantine", f"Items cleaned with \"Quarantine\" are kept here so you can restore them. "
                                     f"They are deleted automatically after {quarantine.RETENTION_DAYS} days. "
                                     "The full record of restored and deleted items stays in the list.")
        self.setObjectName("page")
        QVBoxLayout(self).addWidget(w)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.show_filter = QComboBox()
        self.show_filter.addItems(["In quarantine", "All (quarantine history)", "Restored", "Deleted"])
        self.show_filter.currentIndexChanged.connect(self.refresh)
        self.summary = c.label("", "muted")
        lay.addWidget(c.row(c.button("Restore", self._restore, "primary"),
                            c.button("Delete permanently", self._delete, "danger"),
                            c.button("Open quarantine folder", self._open_folder),
                            self.summary, c.label("Show"), self.show_filter, stretch_at=3))
        self.table = c.table(["Item", "Original location", "Category", "Size", "Quarantined", "Status", "Restored / deleted"], 1)
        lay.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        want = [("Quarantined",), ("Quarantined", "Restored", "Deleted"), ("Restored",), ("Deleted",)][
            self.show_filter.currentIndex()]
        rows = [e for e in quarantine.entries() if e["status"] in want]
        c.fill(self.table, [(os.path.basename(e["original"]), os.path.dirname(e["original"]), e["category"],
                             (fmt_size(e["size"]), e["size"]), (when(e["time"]), e["time"]), e["status"],
                             (when(e["acted"]), e["acted"] or 0)) for e in rows], data=[e["id"] for e in rows])
        active = [e for e in quarantine.entries() if e["status"] == "Quarantined"]
        self.summary.setText(f"{len(active):,} items in quarantine · {fmt_size(sum(e['size'] for e in active))}")

    def _act(self, verb, fn, kind):
        ids = c.selected_data(self.table)
        if not ids:
            QMessageBox.information(self, verb, "Select one or more items first.")
            return
        if kind == "Delete" and not c.confirm(self, "Delete permanently",
                                              f"Permanently delete {len(ids)} item(s)? This cannot be undone."):
            return
        failed = fn(ids)
        n = len(ids) - len(failed)
        history.log(kind, f"{verb} {n} quarantined item(s)" + (f", {len(failed)} failed" if failed else ""), items=n)
        self.refresh()
        self.activity.emit()
        if failed:
            QMessageBox.warning(self, verb, f"{len(failed)} item(s) could not be processed:\n\n" +
                                "\n".join(f"• {why}" for why in list(failed.values())[:10]))

    def _restore(self):
        self._act("Restored", quarantine.restore, "Restore")

    def _delete(self):
        self._act("Deleted", quarantine.delete, "Delete")

    def _open_folder(self):
        os.makedirs(quarantine.ROOT, exist_ok=True)
        osx.reveal_in_file_manager(os.path.join(quarantine.ROOT, "."))


# ===================================================================== history
class HistoryPage(QWidget):
    def __init__(self):
        super().__init__()
        w, lay = _page("History", "Every scan, cleanup, quarantine action and security check, kept on this PC.")
        self.setObjectName("page")
        QVBoxLayout(self).addWidget(w)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.kind = QComboBox()
        self.kind.addItem("All activity")
        self.kind.currentIndexChanged.connect(self._fill)
        self.summary = c.label("", "muted")
        lay.addWidget(c.row(c.label("Show"), self.kind, self.summary, c.button("Export CSV", self._export),
                            c.button("Clear history", self._clear), stretch_at=3))
        self.table = c.table(["Time", "Activity", "Summary", "Items", "Size"], 2)
        lay.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        self.entries = history.load()
        cur = self.kind.currentText()
        kinds = sorted({h["kind"] for h in self.entries})
        self.kind.blockSignals(True)
        self.kind.clear()
        self.kind.addItems(["All activity", *kinds])
        self.kind.setCurrentText(cur if cur in kinds else "All activity")
        self.kind.blockSignals(False)
        self._fill()

    def _shown(self):
        k = self.kind.currentText()
        return [h for h in self.entries if k == "All activity" or h["kind"] == k]

    def _fill(self):
        rows = self._shown()
        c.fill(self.table, [((when(h["time"]), h["time"]), h["kind"], h["summary"],
                             (f"{h['items']:,}" if "items" in h else "", h.get("items", -1)),
                             (fmt_size(h["bytes"]) if "bytes" in h else "", h.get("bytes", -1))) for h in rows])
        freed = freed_bytes(self.entries, quarantine.entries())
        self.summary.setText(f"{len(rows):,} entries · {fmt_size(freed)} freed in total")

    def _export(self):
        rows = self._shown()
        if not rows:
            return
        f, _ = QFileDialog.getSaveFileName(self, "Export history", "junk-cleaner-history.csv", "CSV (*.csv)")
        if f:
            with open(f, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["time", "activity", "summary", "items", "bytes"])
                for h in rows:
                    w.writerow([datetime.fromtimestamp(h["time"]).isoformat(timespec="seconds"), h["kind"],
                                h["summary"], h.get("items", ""), h.get("bytes", "")])

    def _clear(self):
        if c.confirm(self, "Clear history", "Delete the whole activity history? Quarantined files are not affected."):
            history.clear()
            self.refresh()
