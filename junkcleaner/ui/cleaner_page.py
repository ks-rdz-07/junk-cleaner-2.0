"""Cleaner page: choose targets, scan, review, clean (Recycle Bin / quarantine / permanent)."""
import csv
import os
import threading
import time
from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QFileDialog, QGridLayout, QHBoxLayout,
                               QHeaderView, QLineEdit, QListWidget, QMenu, QMessageBox, QRadioButton,
                               QTableView, QToolButton, QVBoxLayout, QWidget, QApplication, QSizePolicy)

from .. import cleaner, history, quarantine, scanner
from .. import platform_os as osx
from ..domain import CATEGORIES, DAY, MB, ScanOptions, fmt_size
from . import common as c
from .theme import CATEGORY_COLORS

HEADERS = ["", "Name", "Category", "Size", "Modified", "Location"]
SORT_KEYS = [lambda i: i.checked, lambda i: i.name.lower(), lambda i: i.category, lambda i: i.size,
             lambda i: i.mtime, lambda i: i.path.lower()]


class JunkModel(QAbstractTableModel):
    changed = Signal()  # checks or contents changed -> update stats

    def __init__(self):
        super().__init__()
        self.items, self.rows = [], []
        self.sort_col, self.sort_rev = 3, True
        self.cats, self.query, self.min_size, self.min_days = set(CATEGORIES), "", 0, 0
        self.icons = {k: c.dot_icon(v) for k, v in CATEGORY_COLORS.items()}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(HEADERS)

    def headerData(self, s, orient, role=Qt.DisplayRole):
        if orient == Qt.Horizontal and role == Qt.DisplayRole:
            return HEADERS[s]
        return None

    def item(self, row):
        return self.items[self.rows[row]]

    def data(self, idx, role=Qt.DisplayRole):
        it, col = self.item(idx.row()), idx.column()
        if role == Qt.DisplayRole:
            if col == 1:
                return it.name
            if col == 2:
                return it.category
            if col == 3:
                return fmt_size(it.size)
            if col == 4:
                return "—" if it.is_recycle_bin else datetime.fromtimestamp(it.mtime).strftime("%Y-%m-%d %H:%M")
            if col == 5:
                return it.location
        elif role == Qt.CheckStateRole and col == 0:
            return Qt.Checked if it.checked else Qt.Unchecked
        elif role == Qt.DecorationRole and col == 2:
            return self.icons.get(it.category)
        elif role == Qt.TextAlignmentRole and col == 3:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        elif role == Qt.ToolTipRole and col in (1, 5):
            return it.path
        return None

    def flags(self, idx):
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return f | Qt.ItemIsUserCheckable if idx.column() == 0 else f

    def setData(self, idx, value, role=Qt.EditRole):
        if role == Qt.CheckStateRole and idx.column() == 0:
            self.item(idx.row()).checked = Qt.CheckState(value) == Qt.Checked
            self.dataChanged.emit(idx, idx, [role])
            self.changed.emit()
            return True
        return False

    def sort(self, col, order=Qt.AscendingOrder):
        self.sort_col, self.sort_rev = col, order == Qt.DescendingOrder
        self.refilter()

    def refilter(self):
        cutoff = time.time() - self.min_days * DAY
        q = self.query.lower()
        rows = [n for n, it in enumerate(self.items)
                if it.category in self.cats and it.size >= self.min_size
                and (self.min_days <= 0 or it.mtime <= cutoff) and (not q or q in it.path.lower())]
        key = SORT_KEYS[self.sort_col]
        rows.sort(key=lambda n: key(self.items[n]), reverse=self.sort_rev)
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()
        self.changed.emit()

    def set_checked(self, rows, value):
        """value True/False sets, None toggles."""
        for r in rows:
            it = self.item(r)
            it.checked = (not it.checked) if value is None else value
        if rows:
            self.dataChanged.emit(self.index(min(rows), 0), self.index(max(rows), 0), [Qt.CheckStateRole])
        self.changed.emit()


class CleanerPage(QWidget):
    activity = Signal()  # history / quarantine changed

    def __init__(self, status):
        super().__init__()
        self.setObjectName("page")
        self.status = status  # main-window Progress
        self.model = JunkModel()
        self.stop = threading.Event()
        self.busy, self.dirty, self.freed_total = None, False, 0
        self.render_timer = QTimer(self, interval=1000, timeout=self._render_if_dirty)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(16)
        outer.addWidget(self._options())
        outer.addWidget(self._results(), 1)
        self.model.changed.connect(self._update_stats)
        self._update_stats()

    # ------------------------------------------------------------ layout
    def _options(self):
        box, lay = c.card(margins=(18, 16, 18, 16), spacing=6)
        box.setFixedWidth(330)
        lay.addWidget(c.label("SCAN TARGETS", "section"))
        self.use_system = QCheckBox("System junk locations")
        self.use_system.setChecked(True)
        lay.addWidget(self.use_system)
        lay.addWidget(c.label("Temp, browser caches, crash dumps, Recycle Bin" if osx.WIN
                              else "/tmp, ~/.cache, thumbnails, crash reports, Trash",  # nosec B108 - label text
                              "muted", wrap=True))
        self.use_worktrees = QCheckBox("Claude agent worktrees")
        lay.addWidget(self.use_worktrees)
        lay.addWidget(c.label("All drives · <repo>/.claude/worktrees/* · never pre-checked", "muted", wrap=True))
        lay.addSpacing(6)
        lay.addWidget(c.label("Custom folders / drives"))
        self.dirs = QListWidget()
        self.dirs.setFixedHeight(80)
        self.dirs.setSelectionMode(QAbstractItemView.ExtendedSelection)
        lay.addWidget(self.dirs)
        lay.addWidget(c.row(c.button("+ Add folder", self._add_dir),
                            c.button("Remove", lambda: [self.dirs.takeItem(self.dirs.row(i))
                                                        for i in self.dirs.selectedItems()]), stretch_at=2))
        lay.addWidget(c.label("Finds logs, backups, temp, empty and large files", "muted", wrap=True))

        lay.addSpacing(10)
        lay.addWidget(c.label("OPTIONS", "section"))
        self.large_mb = c.NumberBox(500, minimum=10)
        lay.addWidget(c.row(c.label("Large file ≥"), self.large_mb, c.label("MB", "muted"), stretch_at=3))
        self.skip_recent = QCheckBox("Skip files changed in last 24 h")
        self.skip_recent.setChecked(True)
        lay.addWidget(self.skip_recent)

        lay.addSpacing(10)
        lay.addWidget(c.label("WHEN CLEANING", "section"))
        self.mode = QButtonGroup(self)
        for i, (text, hint) in enumerate((
                ("Move to Recycle Bin" if osx.WIN else "Move to Trash", "Restore from the system bin"),
                ("Quarantine", f"Restore from the Quarantine page · auto-deleted after {quarantine.RETENTION_DAYS} days"),
                ("Delete permanently", "Cannot be undone"))):
            rb = QRadioButton(text)
            rb.setChecked(i == 0)
            self.mode.addButton(rb, i)
            lay.addWidget(rb)
            lay.addWidget(c.label(hint, "muted", wrap=True))
        lay.addStretch(1)
        return box

    def _results(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.card_found = c.StatCard("Found", "#8b949e")
        self.card_sel = c.StatCard("Selected", "#2f81f7")
        self.card_freed = c.StatCard("Freed this session", "#3fb950")
        for x in (self.card_found, self.card_sel, self.card_freed):
            cards.addWidget(x)
        lay.addLayout(cards)

        bar, bl = c.card(QVBoxLayout, margins=(14, 10, 14, 10))
        self.search = QLineEdit(placeholderText="Search path…", clearButtonEnabled=True)
        self.min_mb, self.min_days = c.NumberBox(0), c.NumberBox(0)
        self.search.setMinimumWidth(150)
        self.search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sel = [c.button(t, lambda v=v: self._check_visible(v)) for t, v in (("All", True), ("None", False),
                                                                             ("Invert", None))]
        bl.addWidget(c.row(self.search, c.label("Min size", "muted"), self.min_mb, c.label("MB", "muted"),
                           c.label("Older than", "muted"), self.min_days, c.label("days", "muted"),
                           c.label("Select", "muted"), *sel, c.button("Export CSV", self._export)))
        chips = QGridLayout()
        chips.setSpacing(6)
        self.chips = {}
        for n, cat in enumerate(CATEGORIES):
            b = QToolButton(objectName="chip", checkable=True, checked=True, cursor=Qt.PointingHandCursor)
            b.setIcon(self.model.icons[cat])
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.toggled.connect(self._filters_changed)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            chips.addWidget(b, n // 5, n % 5)
            self.chips[cat] = b
        bl.addLayout(chips)
        lay.addWidget(bar)

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(3, Qt.DescendingOrder)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(30)
        h = self.table.horizontalHeader()
        h.setHighlightSections(False)
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for col, width in enumerate((36, 240, 170, 90, 140)):
            self.table.setColumnWidth(col, width)
        h.setSectionResizeMode(0, QHeaderView.Fixed)
        h.setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.doubleClicked.connect(lambda _: self._reveal())
        QShortcut(QKeySequence(Qt.Key_Space), self.table, lambda: self.model.set_checked(self._highlighted(), None))
        lay.addWidget(self.table, 1)
        self.info = c.label("", "muted")
        lay.addWidget(self.info)

        self.btn_scan = c.button("Scan", self.start_scan, "primary")
        self.btn_stop = c.button("Stop", self.stop.set)
        self.btn_clean = c.button("Clean selected", self._start_clean, "danger")
        for b in (self.btn_scan, self.btn_stop, self.btn_clean):
            b.setMinimumWidth(120)
        self.btn_stop.setEnabled(False)
        lay.addWidget(c.row(self.btn_scan, self.btn_stop, self.btn_clean, stretch_at=0))

        self.filter_timer = QTimer(self, singleShot=True, interval=200, timeout=self._apply_filters)
        for sig in (self.search.textChanged, self.min_mb.valueChanged, self.min_days.valueChanged):
            sig.connect(self._filters_changed)
        return w

    # ------------------------------------------------------------ filters
    def _filters_changed(self, *_):
        self.filter_timer.start()

    def _apply_filters(self):
        m = self.model
        m.cats = {k for k, b in self.chips.items() if b.isChecked()}
        m.query, m.min_size, m.min_days = self.search.text().strip(), self.min_mb.value() * MB, self.min_days.value()
        m.refilter()

    def _update_stats(self):
        items = self.model.items
        sel = [i for i in items if i.checked]
        self.card_found.set(f"{len(items):,}", fmt_size(sum(i.size for i in items)))
        self.card_sel.set(f"{len(sel):,}", fmt_size(sum(i.size for i in sel)))
        self.card_freed.set(fmt_size(self.freed_total))
        per = {k: [0, 0] for k in CATEGORIES}
        for i in items:
            per[i.category][0] += 1
            per[i.category][1] += i.size
        for k, (n, size) in per.items():
            name = k.replace("&", "&&")  # a lone & would become a keyboard mnemonic
            self.chips[k].setText(f"{name}  ·  {n:,}")
            self.chips[k].setToolTip(f"{k}: {n:,} items, {fmt_size(size)} · click to show/hide")
        n = len(self.model.rows)
        self.info.setText("Press Scan to find junk files." if not items else
                          f"{n:,} of {len(items):,} items match the filters  ·  click a checkbox or press Space to "
                          "toggle  ·  double-click opens the file location")

    # ------------------------------------------------------------ selection
    def _highlighted(self):
        return sorted({i.row() for i in self.table.selectionModel().selectedRows()})

    def _check_visible(self, value):
        self.model.set_checked(range(len(self.model.rows)), value)

    def _menu(self, pos):
        if not self._highlighted():
            return
        m = QMenu(self)
        m.addAction("Check highlighted", lambda: self.model.set_checked(self._highlighted(), True))
        m.addAction("Uncheck highlighted", lambda: self.model.set_checked(self._highlighted(), False))
        m.addSeparator()
        m.addAction("Open file location", self._reveal)
        m.addAction("Copy path", lambda: QApplication.clipboard().setText(
            "\n".join(self.model.item(r).path for r in self._highlighted())))
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _reveal(self):
        rows = self._highlighted()
        if rows and not self.model.item(rows[0]).is_recycle_bin:
            try:
                osx.reveal_in_file_manager(self.model.item(rows[0]).path)
            except OSError as ex:
                QMessageBox.critical(self, "Open location", str(ex))

    def _add_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Choose a folder or drive to scan")
        existing = {self.dirs.item(i).text() for i in range(self.dirs.count())}
        if d and os.path.normpath(d) not in existing:
            self.dirs.addItem(os.path.normpath(d))

    def _export(self):
        rows = self.model.rows
        if not rows:
            QMessageBox.information(self, "Export", "Nothing to export - run a scan first.")
            return
        f, _ = QFileDialog.getSaveFileName(self, "Export", "junk-report.csv", "CSV (*.csv)")
        if not f:
            return
        with open(f, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["selected", "path", "category", "size_bytes", "modified"])
            for n in rows:
                it = self.model.items[n]
                w.writerow([it.checked, it.path, it.category, it.size,
                            datetime.fromtimestamp(it.mtime).isoformat(timespec="seconds")])
        self.status.done(f"Exported {len(rows):,} rows to {f}")

    # ------------------------------------------------------------ workers
    def _set_busy(self, kind):
        self.busy = kind
        self.btn_scan.setEnabled(not kind)
        self.btn_clean.setEnabled(not kind)
        self.btn_stop.setEnabled(kind == "scan")

    def start_scan(self):
        if self.busy:
            return
        folders = tuple(self.dirs.item(i).text() for i in range(self.dirs.count()))
        if not (self.use_system.isChecked() or self.use_worktrees.isChecked() or folders):
            QMessageBox.warning(self, "Scan", "Choose at least one scan target.")
            return
        opts = ScanOptions(self.use_system.isChecked(), folders, self.large_mb.value() * MB,
                           self.skip_recent.isChecked(), self.use_worktrees.isChecked())
        self.model.items = []
        self.model.refilter()
        self.stop.clear()
        self._set_busy("scan")
        self.status.busy("Scanning…")
        self.render_timer.start()
        started = time.time()

        def add(batch):
            self.model.items.extend(batch)
            self.dirty = True
            self.status.message(f"Scanning…  {len(self.model.items):,} items found")

        def work():
            scanner.scan(opts, self.stop, lambda b: c.ui(add, b),
                         lambda d: c.ui(self.status.message, f"Scanning {d}"))
        c.run_bg(work, lambda _: self._finish_scan(started), lambda ex: self._finish_scan(started, ex))

    def _render_if_dirty(self):
        if self.dirty:
            self.dirty = False
            self.model.refilter()

    def _finish_scan(self, started, error=None):
        self.render_timer.stop()
        self._set_busy(None)
        self.model.refilter()
        items = self.model.items
        size = sum(i.size for i in items)
        word = "Failed" if error else ("Stopped" if self.stop.is_set() else "Scan complete")
        self.status.done(f"{word}: {len(items):,} junk items, {fmt_size(size)}. Safe categories are pre-checked - "
                         "review, then press Clean selected." + (f"  ({error})" if error else ""))
        c.notify(f"Junk scan {word.lower()}", f"{len(items):,} junk items, {fmt_size(size)}. Review them, then clean.")
        history.log("Scan", f"{word}: {len(items):,} items, {fmt_size(size)}", items=len(items), bytes=size,
                    seconds=round(time.time() - started))
        self.activity.emit()

    def _start_clean(self):
        sel = [i for i in self.model.items if i.checked]
        if not sel:
            QMessageBox.information(self, "Clean", "No files are checked.")
            return
        mode = self.mode.checkedId()  # 0 bin, 1 quarantine, 2 permanent
        how = [f"moved to the {'Recycle Bin' if osx.WIN else 'Trash'}", "moved to quarantine",
               "PERMANENTLY deleted"][mode]
        if not c.confirm(self, "Confirm cleanup", f"{len(sel):,} items ({fmt_size(sum(i.size for i in sel))}) "
                                                  f"will be {how}.\n\nContinue?"):
            return
        self._set_busy("clean")
        self.status.set(0, len(sel), "Cleaning…")

        def work():
            return cleaner.clean(sel, mode == 0, lambda d, n: c.ui(self.status.set, d, n, f"Cleaning… {d:,} / {n:,}"),
                                 to_quarantine=mode == 1)
        mode_name = ["bin", "quarantine", "delete"][mode]
        c.run_bg(work, lambda r: self._finish_clean(r, how, mode_name),
                 lambda ex: self._finish_clean(None, how, mode_name, ex))

    def _finish_clean(self, result, how, mode, error=None):
        self._set_busy(None)
        if result is None:
            self.model.refilter()
            self.status.done(f"Cleanup stopped: {error}")
            QMessageBox.critical(self, "Cleanup", f"Cleanup stopped because of an error:\n{error}")
            return
        gone = {id(i) for i in result.done}
        self.freed_total += result.freed
        self.model.items = [i for i in self.model.items if id(i) not in gone]
        self.model.refilter()
        errors = result.errors
        summary = f"{len(result.done):,} items {how.replace('PERMANENTLY ', 'permanently ')}, {fmt_size(result.freed)}"
        history.log("Clean", summary + (f", {len(errors):,} skipped" if errors else ""), items=len(result.done),
                    bytes=result.freed, skipped=len(errors), mode=mode)
        self.activity.emit()
        self.status.done(summary + (f", {len(errors):,} skipped." if errors else "."))
        c.notify("Cleanup complete", summary + (f", {len(errors):,} skipped" if errors else ""))
        if errors:
            lines = "\n".join(f"• {p}  ({why})" for p, why in errors[:15])
            extra = f"\n…and {len(errors) - 15:,} more" if len(errors) > 15 else ""
            tip = "Close the apps using them" + (" or run as administrator." if osx.WIN else " or run with sudo.")
            QMessageBox.warning(self, "Some items were skipped", f"{summary}. {len(errors):,} items could not be "
                                f"removed:\n\n{lines}{extra}\n\n{tip}")
        else:
            QMessageBox.information(self, "Cleanup complete", summary + ".")
