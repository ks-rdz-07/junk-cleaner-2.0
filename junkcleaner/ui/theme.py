"""Colours and the Qt style sheet (dark / light)."""
CATEGORY_COLORS = {"Temp files": "#3b82f6", "Cache": "#8b5cf6", "Logs & dumps": "#f59e0b",
                   "System junk": "#64748b", "Backups & leftovers": "#14b8a6", "Trash": "#ef4444",
                   "Empty files": "#94a3b8", "Large files": "#ec4899", "Agent worktrees": "#f97316"}

PALETTES = {
    "dark": dict(bg="#0d1117", side="#090c10", panel="#151b23", field="#0d1117", border="#262e3a",
                 fg="#e6edf3", muted="#8b949e", accent="#2f81f7", accent_hi="#4c94f8", sel="#1f3a5f",
                 hover="#1c2430", ok="#3fb950", warn="#d29922", danger="#f85149", alt="#121820"),
    "light": dict(bg="#f4f6f9", side="#ffffff", panel="#ffffff", field="#ffffff", border="#d8dee6",
                  fg="#1f2328", muted="#656d76", accent="#0969da", accent_hi="#1f7ae8", sel="#dbeafe",
                  hover="#eef2f6", ok="#1a7f37", warn="#9a6700", danger="#cf222e", alt="#f8fafc"),
}
NAME = "dark"
C = dict(PALETTES[NAME])


def use(name):
    global NAME
    NAME = name
    C.clear()
    C.update(PALETTES[name])


def qss(check_svg=""):
    return """
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 10pt; color: %(fg)s; }
QMainWindow, QWidget#page, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget { background: %(bg)s; }
QToolTip { background: %(panel)s; color: %(fg)s; border: 1px solid %(border)s; padding: 4px; }

QFrame#sidebar { background: %(side)s; border-right: 1px solid %(border)s; }
QLabel#brand { font-size: 13pt; font-weight: 600; }
QLabel#brandSub, QLabel#muted { color: %(muted)s; }
QPushButton#nav { text-align: left; padding: 10px 14px; border: none; border-radius: 8px;
                  background: transparent; color: %(muted)s; font-size: 10.5pt; }
QPushButton#nav:hover { background: %(hover)s; color: %(fg)s; }
QPushButton#nav:checked { background: %(sel)s; color: %(fg)s; font-weight: 600; }

QLabel#h1 { font-size: 18pt; font-weight: 600; }
QLabel#h2 { font-size: 11.5pt; font-weight: 600; }
QLabel#section { color: %(muted)s; font-size: 8.5pt; font-weight: 600; letter-spacing: 1px; }
QLabel#statValue { font-size: 16pt; font-weight: 600; }
QLabel#statTitle { color: %(muted)s; font-size: 8.5pt; font-weight: 600; letter-spacing: 1px; }

QFrame#card { background: %(panel)s; border: 1px solid %(border)s; border-radius: 10px; }
QFrame#banner { border-radius: 12px; }

QPushButton { background: %(panel)s; border: 1px solid %(border)s; border-radius: 7px; padding: 7px 16px; }
QPushButton:hover { background: %(hover)s; }
QPushButton:disabled { color: %(muted)s; background: %(bg)s; }
QPushButton#primary { background: %(accent)s; border-color: %(accent)s; color: white; font-weight: 600; }
QPushButton#primary:hover { background: %(accent_hi)s; }
QPushButton#danger { background: %(danger)s; border-color: %(danger)s; color: white; font-weight: 600; }
QPushButton#primary:disabled, QPushButton#danger:disabled { background: %(border)s; border-color: %(border)s; color: %(muted)s; }
QToolButton#chip { background: %(panel)s; border: 1px solid %(border)s; border-radius: 14px; padding: 4px 12px; color: %(muted)s; }
QToolButton#chip:checked { background: %(sel)s; border-color: %(accent)s; color: %(fg)s; }

QLineEdit, QSpinBox, QComboBox { background: %(field)s; border: 1px solid %(border)s; border-radius: 6px; padding: 5px 8px; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: %(accent)s; }
QComboBox QAbstractItemView { background: %(panel)s; border: 1px solid %(border)s; selection-background-color: %(sel)s; }
QListWidget { background: %(field)s; border: 1px solid %(border)s; border-radius: 6px; }
QCheckBox, QRadioButton { spacing: 8px; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator, QTableView::indicator { width: 16px; height: 16px;
    border: 1px solid %(muted)s; background: %(field)s; border-radius: 4px; }
QRadioButton::indicator { border-radius: 9px; }
QCheckBox::indicator:checked, QTableView::indicator:checked { background: %(accent)s; border-color: %(accent)s;
    image: url(%(check)s); }
QRadioButton::indicator:checked { background: %(field)s; border: 5px solid %(accent)s; width: 8px; height: 8px; }

QTableView { background: %(panel)s; alternate-background-color: %(alt)s; border: 1px solid %(border)s;
             border-radius: 10px; gridline-color: transparent; selection-background-color: %(sel)s;
             selection-color: %(fg)s; }
QTableView::item { padding: 4px 6px; border: none; }
QHeaderView::section { background: %(panel)s; color: %(muted)s; border: none; border-bottom: 1px solid %(border)s;
                       padding: 8px 6px; font-weight: 600; }
QTableCornerButton::section { background: %(panel)s; border: none; }

QTabWidget::pane { border: none; }
QTabBar::tab { background: transparent; color: %(muted)s; padding: 9px 18px; border: none;
               border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: %(fg)s; border-bottom: 2px solid %(accent)s; font-weight: 600; }
QTabBar::tab:hover { color: %(fg)s; }

QProgressBar { background: %(border)s; border: none; border-radius: 4px; height: 8px; text-align: center;
               color: transparent; max-height: 8px; }
QProgressBar::chunk { background: %(accent)s; border-radius: 4px; }
QProgressBar#danger::chunk { background: %(danger)s; }
QProgressBar#cell { max-height: 20px; height: 20px; margin: 4px 6px; color: %(fg)s; background: %(field)s;
                    border: 1px solid %(border)s; border-radius: 5px; font-size: 8.5pt; }
QProgressBar#cell::chunk { background: %(sel)s; border-radius: 4px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle { background: %(border)s; border-radius: 4px; min-height: 30px; min-width: 30px; }
QScrollBar::handle:hover { background: %(muted)s; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { background: none; border: none; }
QMenu { background: %(panel)s; border: 1px solid %(border)s; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background: %(sel)s; }
QStatusBar { background: %(side)s; border-top: 1px solid %(border)s; color: %(muted)s; }
""" % dict(C, check=check_svg.replace("\\", "/"))
