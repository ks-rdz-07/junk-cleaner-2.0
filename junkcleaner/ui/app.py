"""Main window: sidebar navigation + pages. Core logic lives outside ui/."""
import os
import sys

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QStackedWidget,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

from .. import __version__, history, quarantine
from .. import platform_os as osx
from . import common as c
from . import theme
from .cleaner_page import CleanerPage
from .pages import DashboardPage, HistoryPage, QuarantinePage
from .security_page import SecurityPage

# assets/ sits next to the package in source, and in sys._MEIPASS when frozen by PyInstaller
ASSETS = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))), "assets")
CHECK = os.path.join(ASSETS, "check.svg")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Junk Cleaner")
        self.resize(1360, 840)
        self.setMinimumSize(1100, 680)
        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.setCentralWidget(root)

        self.progress = c.Progress()  # cleaner status, in the status bar
        sb = self.statusBar()
        sb.addWidget(self.progress, 1)
        sb.setContentsMargins(240, 0, 0, 0)  # line the status text up with the pages, not the sidebar
        sb.setSizeGripEnabled(False)
        self.progress.done("Ready.")

        self.dashboard = DashboardPage()
        self.cleaner = CleanerPage(self.progress)
        self.security = SecurityPage()
        self.quarantine = QuarantinePage()
        self.history = HistoryPage()
        self.stack = QStackedWidget()
        pages = [("Overview", self.dashboard), ("Cleaner", self.cleaner), ("Security", self.security),
                 ("Quarantine", self.quarantine), ("History", self.history)]
        for _, p in pages:
            self.stack.addWidget(p)
        lay.addWidget(self._sidebar([t for t, _ in pages]))
        lay.addWidget(self.stack, 1)

        for p in (self.cleaner, self.security, self.quarantine):
            p.activity.connect(self._activity)
        # tray icon = native Windows notifications when a job finishes; clicking one brings the window back
        self.tray = QSystemTrayIcon(QApplication.windowIcon(), self)
        self.tray.setToolTip("Junk Cleaner")
        self.tray.messageClicked.connect(self._bring_to_front)
        self.tray.activated.connect(lambda reason: self._bring_to_front())
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        c.set_notifier(self._notify)
        self.dashboard.go.connect(self._quick)

    def _sidebar(self, titles):
        side = QFrame(objectName="sidebar")
        side.setFixedWidth(230)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(14, 18, 14, 14)
        lay.setSpacing(4)
        brand = QHBoxLayout()
        logo = os.path.join(ASSETS, "app.png")
        if os.path.exists(logo):
            img = QLabel()
            img.setPixmap(QPixmap(logo).scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            brand.addWidget(img)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(c.label("Junk Cleaner", "brand"))
        names.addWidget(c.label(f"Version {__version__}", "brandSub"))
        brand.addLayout(names, 1)
        lay.addLayout(brand)
        lay.addSpacing(18)
        self.nav = QButtonGroup(self)
        glyphs = [0xE80F, 0xE74D, 0xEA18, 0xE72E, 0xE81C]  # home, delete, shield, lock, history
        for i, t in enumerate(titles):
            b = c.button(f"  {t}", kind="nav")
            b.setIcon(c.glyph_icon(glyphs[i], theme.C["muted"]))
            b.setIconSize(QSize(20, 20))
            b.setCheckable(True)
            b.setChecked(i == 0)
            self.nav.addButton(b, i)
            lay.addWidget(b)
        self.nav.idClicked.connect(self._show)
        lay.addStretch(1)
        who = "Administrator" if osx.is_admin() else "Standard user"
        lay.addWidget(c.label(f"Running as {who}", "brandSub"))
        self.theme_btn = c.button("☀  Light theme", self._toggle_theme)
        lay.addWidget(self.theme_btn)
        return side

    def _notify(self, title, text):
        if self.tray.isVisible():
            self.tray.showMessage(title, text, QSystemTrayIcon.Information, 10000)
        QApplication.alert(self)  # flash the taskbar button if the window is in the background

    def _bring_to_front(self):
        self.showNormal() if self.isMinimized() else self.show()
        self.raise_()
        self.activateWindow()

    def _show(self, i):
        self.nav.button(i).setChecked(True)
        self.stack.setCurrentIndex(i)
        if self.stack.currentWidget() is self.dashboard:
            self.dashboard.refresh()

    def _activity(self):
        self.dashboard.refresh()
        self.history.refresh()
        self.quarantine.refresh()

    def _quick(self, what):
        if what == "scan":
            self._show(1)
            self.cleaner.start_scan()
        elif not osx.WIN:
            self.progress.done("Security checks are Windows only for now.")
        else:
            self._show(2)
            self.security.tabs.setCurrentIndex(0 if what == "virus" else 2)
            self.security.virus_scan(False) if what == "virus" else self.security.check_updates()

    def _toggle_theme(self):
        theme.use("light" if theme.NAME == "dark" else "dark")
        QApplication.instance().setStyleSheet(theme.qss(CHECK))
        self.theme_btn.setText("☀  Light theme" if theme.NAME == "dark" else "☾  Dark theme")
        self.dashboard.refresh()


def run():
    # the frozen exe is elevated by its manifest; from source, relaunch elevated (decline = run as standard user)
    if osx.WIN and not getattr(sys, "frozen", False) and not osx.is_admin() and "--no-elevate" not in sys.argv:
        import ctypes
        main = ["-m", "junkcleaner"] if sys.argv[0].endswith("__main__.py") else [os.path.abspath(sys.argv[0])]
        args = " ".join(f'"{a}"' for a in [*main, *sys.argv[1:], "--no-elevate"])
        if ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, None, 1) > 32:
            return
    app = QApplication(sys.argv)
    app.setApplicationName("Junk Cleaner")
    app.setStyle("Fusion")  # consistent base for the style sheet
    app.setStyleSheet(theme.qss(CHECK))
    icon = os.path.join(ASSETS, "app.png")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    c.init_bridge()
    try:
        purged = quarantine.purge_expired()
        if purged:
            history.log("Delete", f"Auto-deleted {purged} quarantined item(s) older than "
                                  f"{quarantine.RETENTION_DAYS} days", items=purged)
    except OSError:
        pass  # never block startup on quarantine housekeeping
    w = MainWindow()
    w.showMaximized()
    if "--screenshot" in sys.argv:  # dev aid: python -m junkcleaner --no-elevate --screenshot out.png [page]
        i = sys.argv.index("--screenshot")
        page = int(sys.argv[i + 2]) if len(sys.argv) > i + 2 else 0
        if "--light" in sys.argv:
            w._toggle_theme()
        QTimer.singleShot(2500, lambda: (w._show(page), QTimer.singleShot(
            800, lambda: (w.grab().save(sys.argv[i + 1]), app.quit()))))
    sys.exit(app.exec())
