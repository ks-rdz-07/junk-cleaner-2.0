"""Brand kit + drawing helpers shared by images.py and video.py (QPainter, no extra dependencies)."""
import os

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath,
                           QPen, QRadialGradient)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHOTS = os.path.join(HERE, "shots")
LOGO = os.path.join(ROOT, "assets", "app.png")

INK = "#060a12"        # background
NAVY = "#0b1324"
BLUE = "#2f81f7"
CYAN = "#38bdf8"
GREEN = "#3fb950"
VIOLET = "#8b5cf6"
AMBER = "#d29922"
RED = "#f85149"
WHITE = "#f0f6fc"
MUTED = "#9aa7b8"
PALETTE = [("Ink", INK), ("Navy", NAVY), ("Signal Blue", BLUE), ("Sky", CYAN), ("Safe Green", GREEN),
           ("Violet", VIOLET), ("Amber", AMBER), ("Alert Red", RED), ("Cloud", WHITE)]
DISPLAY = "Segoe UI Variable Display"
TEXT = "Segoe UI"

TAGLINE = "Clean junk. Undo anything. Basic security checks built in."
FEATURES = [("Clean", "Find temp files, caches, crash dumps and leftovers. Review every item before it goes.", GREEN),
            ("Check", "Basic security checks: antivirus and firewall status, Microsoft's on-demand scanner, missing patches.", BLUE),
            ("Update", "Update outdated apps in parallel with live progress on every row.", VIOLET),
            ("Undo", "Quarantine keeps cleaned files restorable for 30 days, with a full history.", AMBER)]

_cache = {}


def shot(name):
    if name not in _cache:
        img = QImage(os.path.join(SHOTS, name + ".png"))
        if img.isNull():
            raise SystemExit(f"Missing marketing/shots/{name}.png - run: python marketing/capture.py")
        _cache[name] = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    return _cache[name]


def logo():
    return shot_path(LOGO)


def shot_path(path):
    if path not in _cache:
        _cache[path] = QImage(path).convertToFormat(QImage.Format_ARGB32_Premultiplied)
    return _cache[path]


def blur(img, amount):
    """Cheap gaussian-like blur: scale down then smoothly back up (twice). amount ~ radius in px."""
    key = (img.cacheKey(), amount)
    if key in _cache:
        return _cache[key]
    w, h = img.width(), img.height()
    f = max(1.0, amount / 2)
    small = img.scaled(max(1, int(w / f)), max(1, int(h / f)), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    small = small.scaled(max(1, int(w / f / 1.5)), max(1, int(h / f / 1.5)), Qt.IgnoreAspectRatio,
                         Qt.SmoothTransformation)
    out = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    _cache[key] = out
    return out


def canvas(w, h):
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(INK))
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
    return img, p


def backdrop(p, w, h, screen=None, blur_px=28, dim=0.78, glow=True, t=0.0):
    """Dark brand background: optional heavily blurred screenshot, dimmed, plus soft colour glows."""
    p.fillRect(0, 0, w, h, QColor(INK))
    if screen is not None:
        img = blur(shot(screen), blur_px)
        p.setOpacity(1 - dim)
        draw_cover(p, img, QRectF(0, 0, w, h))
        p.setOpacity(1)
    if glow:
        for cx, cy, r, col, a in ((0.15 + 0.03 * t, 0.2, 0.55, BLUE, 90), (0.9 - 0.03 * t, 0.85, 0.6, VIOLET, 70),
                                  (0.75, 0.05, 0.35, CYAN, 45)):
            g = QRadialGradient(QPointF(cx * w, cy * h), r * max(w, h))
            c = QColor(col)
            c.setAlpha(a)
            g.setColorAt(0, c)
            c.setAlpha(0)
            g.setColorAt(1, c)
            p.fillRect(0, 0, w, h, QBrush(g))
    vignette = QLinearGradient(0, 0, 0, h)
    vignette.setColorAt(0, QColor(6, 10, 18, 0))
    vignette.setColorAt(1, QColor(6, 10, 18, 150))
    p.fillRect(0, 0, w, h, QBrush(vignette))


def draw_cover(p, img, rect):
    """Draw img scaled to cover rect (crop overflow)."""
    s = max(rect.width() / img.width(), rect.height() / img.height())
    sw, sh = rect.width() / s, rect.height() / s
    src = QRectF((img.width() - sw) / 2, (img.height() - sh) / 2, sw, sh)
    p.drawImage(rect, img, src)


def window(p, img, rect, radius=14, src=None, shadow=True, title=True, soften=0.0):
    """App window: drop shadow, title bar, rounded screenshot. soften>0 blurs the screen slightly."""
    r = QRectF(rect)
    if shadow:
        for i in range(14, 0, -1):
            c = QColor(0, 0, 0, int(10 + 3 * (14 - i)))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(r.adjusted(-i, -i + 14, i, i + 18), radius + i, radius + i)
    bar = 34 * r.width() / 1600 if title else 0
    path = QPainterPath()
    path.addRoundedRect(r, radius, radius)
    p.save()
    p.setClipPath(path, Qt.IntersectClip)  # keep any clip the caller set (e.g. the theme split)
    p.fillRect(r, QColor("#090c10"))
    if title:
        p.fillRect(QRectF(r.left(), r.top(), r.width(), bar), QColor("#0b0f15"))
        lg = logo()
        s = bar * 0.55
        p.drawImage(QRectF(r.left() + bar * 0.45, r.top() + (bar - s) / 2, s, s), lg)
        f = QFont(TEXT)
        f.setPixelSize(max(6, int(bar * 0.36)))
        p.setFont(f)
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(r.left() + bar * 1.2, r.top(), r.width(), bar), Qt.AlignVCenter, "Junk Cleaner")
        for i, ch in enumerate(("✕", "▢", "—")):
            p.drawText(QRectF(r.right() - bar * (1.3 + i * 1.4), r.top(), bar, bar), Qt.AlignCenter, ch)
    screen = blur(img, soften) if soften else img
    src = src or QRectF(0, 0, img.width(), img.height())
    p.drawImage(QRectF(r.left(), r.top() + bar, r.width(), r.height() - bar), screen, src)
    p.restore()
    p.setPen(QPen(QColor(255, 255, 255, 30), 1))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(r, radius, radius)


def text(p, s, x, y, size, color=WHITE, weight=QFont.Normal, family=TEXT, width=None, align=Qt.AlignLeft,
         opacity=1.0, spacing=0.0):
    """Draw text with its top-left at x,y (wraps when width is given). Returns the drawn height."""
    f = QFont(family)
    f.setPixelSize(int(size))
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    p.setFont(f)
    c = QColor(color)
    p.setPen(c)
    p.setOpacity(opacity)
    fm = QFontMetricsF(f)
    if width:
        br = fm.boundingRect(QRectF(0, 0, width, 10000), int(align | Qt.TextWordWrap), s)
        p.drawText(QRectF(x, y, width, br.height() + 4), int(align | Qt.TextWordWrap), s)
        h = br.height()
    else:
        p.drawText(QPointF(x, y + fm.ascent()), s)
        h = fm.height()
    p.setOpacity(1)
    return h


def text_width(s, size, weight=QFont.Normal, family=TEXT):
    f = QFont(family)
    f.setPixelSize(int(size))
    f.setWeight(weight)
    return QFontMetricsF(f).horizontalAdvance(s)


def gradient_text(p, s, x, y, size, c1=WHITE, c2=CYAN, weight=QFont.Bold, family=DISPLAY):
    f = QFont(family)
    f.setPixelSize(int(size))
    f.setWeight(weight)
    fm = QFontMetricsF(f)
    path = QPainterPath()
    path.addText(QPointF(x, y + fm.ascent()), f, s)
    g = QLinearGradient(x, y, x + fm.horizontalAdvance(s), y + fm.height())
    g.setColorAt(0, QColor(c1))
    g.setColorAt(1, QColor(c2))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawPath(path)
    return fm.height()


def pill(p, s, x, y, size, color=BLUE, fg=WHITE, fill_alpha=40):
    """Rounded tag. Returns its width."""
    w = text_width(s, size, QFont.DemiBold) + size * 1.6
    h = size * 2.0
    c = QColor(color)
    c.setAlpha(fill_alpha)
    p.setBrush(c)
    c.setAlpha(160)
    p.setPen(QPen(c, max(1, size / 12)))
    p.drawRoundedRect(QRectF(x, y, w, h), h / 2, h / 2)
    text(p, s, x + size * 0.8, y + (h - size * 1.33) / 2, size, fg, QFont.DemiBold)
    return w


def brand_mark(p, x, y, size, name=True, sub=None):
    """Logo + wordmark. size = logo height."""
    p.drawImage(QRectF(x, y, size, size), logo())
    if name:
        text(p, "Junk Cleaner", x + size * 1.25, y + size * 0.02, size * 0.62, WHITE, QFont.DemiBold, DISPLAY)
        if sub:
            text(p, sub, x + size * 1.27, y + size * 0.66, size * 0.26, MUTED)


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_io(t):
    t = max(0.0, min(1.0, t))
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
