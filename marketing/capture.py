"""Screenshots of every page filled with neutral demo data (no real machine, user or path names).
Run from the repo root:  python marketing/capture.py   -> marketing/shots/*.png"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from junkcleaner import history, quarantine  # noqa: E402
from junkcleaner import platform_os as osx  # noqa: E402
from junkcleaner import security as sec  # noqa: E402
from junkcleaner.domain import MB, JunkItem  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
GB = 1024 * MB
NOW = time.time()
HOME = r"C:\Users\Customer"
random.seed(7)

# ------------------------------------------------------------------ demo data
osx.is_admin = lambda: True
osx.system_info = lambda: {"host": "WORKSTATION-01", "os": "Windows 11  (build 26100)",
                           "cpu": "Intel(R) Core(TM) i7-13700H  ·  20 threads", "ram": (9.4 * GB, 32 * GB),
                           "drives": [("C:\\", 312 * GB, 512 * GB), ("D:\\", 610 * GB, 1000 * GB)]}
sec.protection_status = lambda: {"antivirus": [{"name": "Microsoft Defender", "enabled": True, "up_to_date": True}],
                                 "firewall": [{"name": n, "enabled": True} for n in ("Domain", "Private", "Public")]}
HIST = [
    (0.1, "Virus scan", "Quick scan, 6 min: no threats found", {}),
    (0.3, "Apps", "Updated 4 of 4 app(s)", {}),
    (0.5, "Clean", "1,842 items moved to quarantine, 3.1 GB", {"items": 1842, "bytes": int(3.1 * GB)}),
    (0.6, "Scan", "Scan complete: 2,318 items, 4.7 GB", {"items": 2318, "bytes": int(4.7 * GB)}),
    (26, "Restore", "Restored 2 quarantined item(s)", {"items": 2}),
    (49, "Updates", "Windows is up to date", {}),
    (50, "Clean", "6,204 items moved to the Recycle Bin, 8.9 GB", {"items": 6204, "bytes": int(8.9 * GB)}),
    (50.2, "Scan", "Scan complete: 6,950 items, 9.6 GB", {"items": 6950, "bytes": int(9.6 * GB)}),
    (120, "Virus scan", "Full scan, 94 min: no threats found", {}),
]
history.load = lambda: [{"time": NOW - h * 3600, "kind": k, "summary": s, **d} for h, k, s, d in HIST]
Q = [("app-cache-0412.tmp", r"AppData\Local\Temp", "Temp files", 48 * MB, "Quarantined"),
     ("crash-2026-10-28.dmp", r"AppData\Local\CrashDumps", "Logs & dumps", 412 * MB, "Quarantined"),
     ("installer-old.msi.bak", r"Downloads", "Backups & leftovers", 220 * MB, "Quarantined"),
     ("render-preview.tmp", r"AppData\Local\Temp", "Temp files", 96 * MB, "Quarantined"),
     ("thumbcache_1024.db", r"AppData\Local\Microsoft\Windows\Explorer", "Cache", 64 * MB, "Restored"),
     ("setup-log.txt.old", r"Documents\Projects", "Backups & leftovers", 3 * MB, "Deleted")]
quarantine.entries = lambda: [{"id": str(n), "original": os.path.join(HOME, d, f), "size": s, "category": cat,
                               "time": NOW - (n + 1) * 7200, "status": st,
                               "acted": None if st == "Quarantined" else NOW - n * 3000}
                              for n, (f, d, cat, s, st) in enumerate(Q)]


def junk_items():
    spec = [("Temp files", r"AppData\Local\Temp", [".tmp", ".temp"], 2 * MB),
            ("Cache", r"AppData\Local\Google\Chrome\User Data\Default\Cache\Cache_Data", ["", ".dat"], 4 * MB),
            ("Logs & dumps", r"AppData\Local\CrashDumps", [".dmp", ".log"], 60 * MB),
            ("System junk", r"Pictures\Archive", ["thumbs.db"], 1 * MB),
            ("Backups & leftovers", r"Documents\Projects", [".bak", ".old"], 8 * MB),
            ("Large files", r"Downloads", [".iso", ".zip"], 600 * MB)]
    items = []
    for cat, folder, exts, avg in spec:
        for n in range(3 if cat == "Large files" else random.randint(14, 30)):
            ext = random.choice(exts)
            name = ext if ext == "thumbs.db" else f"{random.choice(['f', 'data', 'tmp', 'session', 'build'])}_" \
                                                  f"{random.randint(1000, 99999):x}{ext}"
            items.append(JunkItem(os.path.join(HOME, folder, name), int(avg * random.uniform(0.2, 2.5)),
                                  NOW - random.uniform(2, 90) * 86400, cat, cat not in ("Backups & leftovers",
                                                                                      "Large files")))
    items.append(JunkItem("::RECYCLE_BIN::", int(1.4 * GB), NOW, "Trash", True))
    return items


APPS = [("Visual Studio Code", "Microsoft.VisualStudioCode", "1.104.0", "1.105.1"),
        ("Git", "Git.Git", "2.55.0", "2.56.0"),
        ("7-Zip", "7zip.7zip", "24.09", "25.01"),
        ("Node.js LTS", "OpenJS.NodeJS.LTS", "22.11.0", "22.20.0"),
        ("Python 3.13", "Python.Python.3.13", "3.13.5", "3.13.8"),
        ("PowerToys", "Microsoft.PowerToys", "0.94.0", "0.95.1")]


def main(theme_name="dark"):
    from junkcleaner.ui import common as c
    from junkcleaner.ui import theme
    from junkcleaner.ui.app import CHECK, MainWindow
    os.makedirs(OUT, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    theme.use(theme_name)
    app.setStyleSheet(theme.qss(CHECK))
    c.init_bridge()
    w = MainWindow()
    w.resize(1600, 960)
    w.show()
    suffix = "" if theme_name == "dark" else "-light"
    if theme_name == "light":
        w.theme_btn.setText("☾  Dark theme")

    def shoot(page, name, prep=lambda: None):
        w._show(page)
        prep()
        for _ in range(5):
            app.processEvents()
        w.grab().save(os.path.join(OUT, f"{name}{suffix}.png"))

    def cleaner():
        p = w.cleaner
        p.model.items = junk_items()
        p.freed_total = int(12.0 * GB)
        p.table.sortByColumn(2, Qt.DescendingOrder)  # group by category so the checks show
        from junkcleaner.domain import fmt_size
        n, size = len(p.model.items), sum(i.size for i in p.model.items)
        p.status.done(f"Scan complete: {n:,} junk items, {fmt_size(size)}. Safe categories are pre-checked - "
                      "review, then press Clean selected.")

    def apps():
        s = w.security
        s.tabs.setCurrentIndex(3)
        s.parallel.setCurrentIndex(2)
        w.progress.done("Ready.")
        c.fill(s.atable, [(n, i, v, a, "winget", "") for n, i, v, a in APPS], data=[a[1] for a in APPS],
               checkable=True)
        s.atable.setSortingEnabled(False)  # keep the APPS order so the progress rows below match
        s.atable.horizontalHeader().setSortIndicatorShown(False)
        s.atable.setColumnWidth(5, 340)
        for r in range(5):
            s.atable.item(r, 0).setCheckState(Qt.Checked)
        s._row_result(0, True, "Successfully installed")
        s._row_progress(1, 72, "Downloading 48.6 MB / 67.1 MB")
        s._row_progress(2, 100, "Installing…")
        s._row_progress(3, 31, "Downloading 9.4 MB / 30.2 MB")
        s.atable.item(4, 5).setText("Queued")
        s.progress.set(57, 100, "Updating apps: 1 of 5 done, 4 left  ·  57% overall")

    def go():
        w.dashboard._set_av(sec.protection_status())
        w.dashboard.refresh()
        shoot(0, "overview")
        shoot(1, "cleaner", cleaner)
        shoot(2, "security", apps)
        shoot(3, "quarantine", lambda: w.quarantine.show_filter.setCurrentIndex(1))
        shoot(4, "history", w.history.refresh)
        app.quit()
    QTimer.singleShot(600, go)
    app.exec()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dark")
