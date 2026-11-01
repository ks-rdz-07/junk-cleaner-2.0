"""Small shared Qt helpers: background jobs, cards, tables, dialogs."""
import threading
import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QIntValidator, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)


class _Bridge(QObject):
    call = Signal(object)


_bridge = None


def init_bridge():
    global _bridge
    _bridge = _Bridge()
    _bridge.call.connect(lambda fn: fn())


def ui(fn, *args):
    """Run fn(*args) on the UI thread (safe to call from any thread)."""
    _bridge.call.emit(lambda: fn(*args))


def run_bg(fn, done, fail):
    """fn() on a worker thread; then done(result) or fail(exception) on the UI thread."""
    def work():
        try:
            r = fn()
        except Exception as ex:  # shown to the user, never swallowed
            ui(fail, ex)
        else:
            ui(done, r)
    threading.Thread(target=work, daemon=True).start()


# ------------------------------------------------------------------ widgets
def label(text="", name=None, wrap=False):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def button(text, slot=None, kind=None):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    if kind:
        b.setObjectName(kind)
    if slot:
        b.clicked.connect(lambda *_: slot())
    return b


def card(layout_cls=QVBoxLayout, margins=(16, 14, 16, 14), spacing=8):
    f = QFrame()
    f.setObjectName("card")
    lay = layout_cls(f)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return f, lay


def row(*widgets, spacing=8, stretch_at=None):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for i, x in enumerate(widgets):
        if i == stretch_at:
            lay.addStretch(1)
        lay.addWidget(x)
    if stretch_at == len(widgets):
        lay.addStretch(1)
    return w


class NumberBox(QLineEdit):
    """Whole-number field. Same look as other inputs (QSpinBox styling is unreliable under style sheets)."""
    def __init__(self, value=0, minimum=0, maximum=100000):
        super().__init__(str(value))
        self.minimum = minimum
        self.setValidator(QIntValidator(0, maximum, self))
        self.setFixedWidth(72)
        self.valueChanged = self.textChanged

    def value(self):
        return max(self.minimum, int(self.text() or 0))


class StatCard(QFrame):
    def __init__(self, title, color):
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(f"QFrame#card {{ border-left: 3px solid {color}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(2)
        lay.addWidget(label(title.upper(), "statTitle"))
        self.value = label("—", "statValue")
        self.note = label("", "muted", wrap=True)
        lay.addWidget(self.value)
        lay.addWidget(self.note)

    def set(self, value, note=""):
        self.value.setText(value)
        self.note.setText(note or " ")  # keep height so cards line up


def dot_icon(color, size=10):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.end()
    return QIcon(pm)


def glyph_icon(code, color, size=20):
    """Icon from the Windows icon font (Segoe Fluent Icons / MDL2). Empty icon where the font is missing."""
    from PySide6.QtGui import QFont, QFontDatabase
    fam = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in QFontDatabase.families()), None)
    if not fam:
        return QIcon()
    pm = QPixmap(size * 2, size * 2)  # 2x for high-DPI screens
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setFont(QFont(fam, int(size * 0.62)))
    p.setPen(QColor(color))
    p.drawText(0, 0, size, size, Qt.AlignCenter, chr(code))
    p.end()
    return QIcon(pm)


class _Item(QTableWidgetItem):
    """Cell that sorts by a key (e.g. bytes) while showing text (e.g. '1.5 MB')."""
    def __init__(self, text, key):
        super().__init__(str(text))
        self.key = key

    def __lt__(self, other):
        try:
            return self.key < other.key
        except TypeError:
            return str(self.key) < str(other.key)


def table(headers, stretch=-1):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().hide()
    t.verticalHeader().setDefaultSectionSize(32)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.setWordWrap(False)
    h = t.horizontalHeader()
    h.setHighlightSections(False)
    h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    h.setSectionResizeMode(QHeaderView.Interactive)
    h.setSectionResizeMode(stretch % len(headers), QHeaderView.Stretch)
    return t


def fill(t, rows, data=None, checkable=False):
    """rows: lists of cell values, or (text, sort_key) tuples. data[i] is stored on the row's first cell,
    which gets a checkbox when checkable."""
    t.setSortingEnabled(False)
    t.setRowCount(len(rows))
    for r, cells in enumerate(rows):
        for c, v in enumerate(cells):
            text, key = v if isinstance(v, tuple) else (v, v)
            it = _Item("" if text is None else text, key if key is not None else "")
            it.setToolTip(str(text))
            if c == 0 and data is not None:
                it.setData(Qt.UserRole, data[r])
            if c == 0 and checkable:
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Unchecked)
            t.setItem(r, c, it)
    t.setSortingEnabled(True)
    t.resizeColumnsToContents()
    t.horizontalHeader().setStretchLastSection(True)


def selected_data(t):
    return [t.item(r, 0).data(Qt.UserRole) for r in sorted({i.row() for i in t.selectedIndexes()})]


def checked_data(t):
    return [t.item(r, 0).data(Qt.UserRole) for r in range(t.rowCount()) if t.item(r, 0).checkState() == Qt.Checked]


def set_all_checked(t, on):
    for r in range(t.rowCount()):
        t.item(r, 0).setCheckState(Qt.Checked if on else Qt.Unchecked)


def confirm(parent, title, text):
    """Yes/No with No as the default - nothing destructive happens on a stray Enter."""
    box = QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Yes | QMessageBox.No, parent)
    box.setDefaultButton(QMessageBox.No)
    return box.exec() == QMessageBox.Yes


class Progress(QWidget):
    """Progress bar + status text. Determinate (set) or busy with an elapsed-time counter (busy)."""
    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.bar = QProgressBar()
        self.bar.setFixedWidth(220)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.hide()
        self.text = label("", "muted")
        lay.addWidget(self.bar)
        lay.addWidget(self.text, 1)
        self._start, self._msg = None, ""
        self._timer = QTimer(self, interval=1000, timeout=self._tick)

    def busy(self, msg):
        self.bar.show()
        self.bar.setRange(0, 0)
        self._start, self._msg = time.time(), msg
        self._timer.start()
        self._tick()

    def set(self, value, total, msg):
        self._timer.stop()
        self.bar.show()
        self.bar.setRange(0, max(total, 1))
        self.bar.setValue(value)
        self.text.setText(msg)

    def message(self, msg):  # keep the bar, change the text (elapsed counter keeps running if busy)
        self._msg = msg
        if self._timer.isActive():
            self._tick()
        else:
            self.text.setText(msg)

    def done(self, msg):
        self._timer.stop()
        self.bar.setRange(0, 100)
        self.bar.hide()
        self.text.setText(msg)

    def _tick(self):
        s = int(time.time() - self._start)
        self.text.setText(f"{self._msg}   ·   {s // 3600:d}:{s // 60 % 60:02d}:{s % 60:02d} elapsed")


# ------------------------------------------------------------ notifications
_notifier = None


def set_notifier(fn):
    global _notifier
    _notifier = fn


def notify(title, text):
    """Desktop notification when a job finishes (no-op until the main window installs a notifier)."""
    if _notifier:
        _notifier(title, text)
