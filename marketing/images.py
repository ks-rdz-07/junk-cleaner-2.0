"""Marketing images -> docs/images/. Run after capture.py:  python marketing/images.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import brand as b  # noqa: E402

OUT = os.path.join(b.ROOT, "docs", "images")

# regions of a page screenshot, as fractions (x, y, w, h)
CROPS = {"overview": (0.155, 0.055, 0.845, 0.235), "cleaner": (0.385, 0.0, 0.615, 0.62),
         "security": (0.155, 0.265, 0.845, 0.27), "quarantine": (0.155, 0.0, 0.83, 0.42)}


def crop(name):
    img = b.shot(name)
    x, y, w, h = CROPS[name]
    return QRectF(x * img.width(), y * img.height(), w * img.width(), h * img.height())


def save(img, name):
    """Writes JPEG (quality 90): 95%+ smaller than PNG for these gradients and screenshots, and accepted
    by GitHub's social preview upload, Open Graph and print vendors."""
    os.makedirs(OUT, exist_ok=True)
    name = os.path.splitext(name)[0] + ".jpg"
    img.convertToFormat(img.Format.Format_RGB32).save(os.path.join(OUT, name), "JPG", 90)
    print("wrote", os.path.relpath(os.path.join(OUT, name), b.ROOT))


def headline(p, x, y, size, lines=("Clean junk.", "Undo anything.")):
    for i, ln in enumerate(lines):
        if i == len(lines) - 1:
            y += b.gradient_text(p, ln, x, y, size, b.CYAN, b.BLUE)
        else:
            y += b.gradient_text(p, ln, x, y, size, b.WHITE, "#c9d6e8")
    return y


def wide(w, h, pills=True):
    """Hero / social preview layout: copy on the left, product windows on the right."""
    img, p = b.canvas(w, h)
    b.backdrop(p, w, h, "cleaner", blur_px=int(w / 40))
    u = h / 1080
    b.window(p, b.shot("cleaner"), QRectF(w * 0.50, h * 0.08, w * 0.56, w * 0.56 * 0.611), 14 * u, soften=2.5 * u)
    b.window(p, b.shot("overview"), QRectF(w * 0.44, h * 0.33, w * 0.6, w * 0.6 * 0.611), 16 * u)
    b.brand_mark(p, w * 0.055, h * 0.09, 72 * u, sub="for Windows & Linux")
    y = headline(p, w * 0.055, h * 0.28, 92 * u)
    b.text(p, "A free, open-source junk cleaner with a safety net: review before you delete and restore from "
              "quarantine. Plus basic security checks. Not a replacement for your antivirus.", w * 0.057,
           y + 22 * u, 27 * u, b.MUTED, width=w * 0.36)
    if pills:
        x = w * 0.057
        for s, c in (("Beta", b.AMBER), ("Free & open source", b.GREEN), ("Apache-2.0", b.BLUE),
                     ("No telemetry", b.VIOLET)):
            x += b.pill(p, s, x, h * 0.84, 20 * u, c) + 14 * u
    p.end()
    return img


def billboard(w=3840, h=1280):
    img, p = b.canvas(w, h)
    b.backdrop(p, w, h, "overview", blur_px=60)
    u = h / 1280
    b.window(p, b.shot("overview"), QRectF(w * 0.53, h * 0.12, w * 0.5, w * 0.5 * 0.611), 26 * u, soften=1.5)
    b.brand_mark(p, w * 0.05, h * 0.12, 150 * u)
    y = headline(p, w * 0.05, h * 0.36, 210 * u, ("Clean junk.", "Undo anything."))
    b.text(p, "Free  ·  Open source  ·  Beta", w * 0.052, y + 40 * u, 54 * u, b.MUTED, QFont.DemiBold)
    p.end()
    return img


def square(w=1080):
    img, p = b.canvas(w, w)
    b.backdrop(p, w, w, "security", blur_px=30)
    u = w / 1080
    b.brand_mark(p, 70 * u, 70 * u, 64 * u)
    y = headline(p, 70 * u, 190 * u, 84 * u)
    x = 70 * u + b.pill(p, "Beta", 72 * u, y + 24 * u, 18 * u, b.AMBER) + 16 * u
    b.text(p, "Junk cleaner with basic security checks", x, y + 26 * u, 26 * u, b.MUTED)
    b.window(p, b.shot("security"), QRectF(70 * u, y + 110 * u, 1100 * u, 1100 * u * 0.611), 16 * u)
    p.end()
    return img


def feature(title, desc, color, shot_name, w=1200, h=720):
    img, p = b.canvas(w, h)
    b.backdrop(p, w, h, shot_name, blur_px=36, dim=0.85)
    u = w / 1200
    b.pill(p, title.upper(), 60 * u, 52 * u, 18 * u, color)
    b.text(p, desc, 60 * u, 112 * u, 38 * u, b.WHITE, QFont.DemiBold, b.DISPLAY, width=w - 120 * u)
    src = crop(shot_name)
    rw = w - 120 * u
    rh = rw * src.height() / src.width()
    top = h - rh - 30 * u if rh < h * 0.62 else 300 * u
    b.window(p, b.shot(shot_name), QRectF(60 * u, top, rw, rh), 12 * u, src=src, title=False)
    p.end()
    return img


def feature_grid(w=1920, h=1200):
    img, p = b.canvas(w, h)
    b.backdrop(p, w, h, None)
    u = w / 1920
    b.text(p, "Clean junk safely, with basic security checks", 0, 60 * u, 52 * u, b.WHITE, QFont.DemiBold,
           b.DISPLAY, width=w, align=Qt.AlignHCenter)
    shots = ["cleaner", "overview", "security", "quarantine"]
    cw, ch, gap = (w - 3 * 60 * u) / 2, (h - 220 * u - 60 * u) / 2, 60 * u
    for i, ((title, desc, color), name) in enumerate(zip(b.FEATURES, shots)):
        x, y = 60 * u + (i % 2) * (cw + gap), 180 * u + (i // 2) * (ch + 40 * u)
        card = QRectF(x, y, cw, ch)
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        p.setBrush(QColor(21, 27, 35, 210))
        p.drawRoundedRect(card, 18 * u, 18 * u)
        b.pill(p, title.upper(), x + 30 * u, y + 28 * u, 16 * u, color)
        th = b.text(p, desc, x + 30 * u, y + 76 * u, 24 * u, b.WHITE, width=cw - 60 * u)
        top = y + 76 * u + th + 24 * u
        iw, ih = cw - 60 * u, y + ch - 28 * u - top
        src = crop(name)
        src.setHeight(min(b.shot(name).height() - src.top(), src.width() * ih / iw))  # fill the card from the top
        iw = min(iw, ih * src.width() / src.height())
        b.window(p, b.shot(name), QRectF(x + 30 * u, top, iw, ih), 10 * u, src=src, title=False, shadow=False)
    p.end()
    return img


def themes(w=1920, h=1080):
    """Dark and light theme, split diagonally."""
    img, p = b.canvas(w, h)
    b.backdrop(p, w, h, None)
    u = w / 1920
    rh = h - 190 * u  # fit under the title with a bottom margin
    rw = rh / 0.611
    r = QRectF((w - rw) / 2, 150 * u, rw, rh)
    b.window(p, b.shot("overview"), r, 16 * u)
    path = QPainterPath()
    path.moveTo(r.left() + r.width() * 0.62, r.top())
    path.lineTo(r.right() + 2, r.top())
    path.lineTo(r.right() + 2, r.bottom())
    path.lineTo(r.left() + r.width() * 0.38, r.bottom())
    p.save()
    p.setClipPath(path)
    b.window(p, b.shot("overview-light"), r, 16 * u, shadow=False)
    p.restore()
    p.setPen(QPen(QColor(b.CYAN), 3 * u))
    p.drawLine(r.left() + r.width() * 0.62, r.top(), r.left() + r.width() * 0.38, r.bottom())
    b.text(p, "Dark or light. Your call.", 0, 50 * u, 54 * u, b.WHITE, QFont.DemiBold, b.DISPLAY, width=w,
           align=Qt.AlignHCenter)
    p.end()
    return img


def brand_sheet(w=1920, h=1080):
    """2x2 grid of cards: brand, colour, type, voice. Every text block wraps inside its card."""
    img, p = b.canvas(w, h)
    b.backdrop(p, w, h, None)
    u = w / 1920
    m, gap = 60 * u, 30 * u
    cw = (w - 2 * m - gap) / 2
    top_h, bot_h = 560 * u, h - 2 * m - gap - 560 * u
    cards = {"BRAND": QRectF(m, m, cw, top_h), "COLOUR": QRectF(m + cw + gap, m, cw, top_h),
             "TYPE": QRectF(m, m + top_h + gap, cw, bot_h), "VOICE": QRectF(m + cw + gap, m + top_h + gap, cw, bot_h)}
    pad = 36 * u
    for title, r in cards.items():
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.setBrush(QColor(21, 27, 35, 200))
        p.drawRoundedRect(r, 18 * u, 18 * u)
        b.text(p, title, r.left() + pad, r.top() + pad - 6 * u, 16 * u, b.MUTED, QFont.DemiBold, spacing=4 * u)

    # brand: logo + wordmark, tagline below, logo on three backgrounds, usage note
    r = cards["BRAND"]
    x, y = r.left() + pad, r.top() + pad + 34 * u
    p.drawImage(QRectF(x, y, 96 * u, 96 * u), b.logo())
    b.text(p, "Junk Cleaner", x + 120 * u, y + 2 * u, 58 * u, b.WHITE, QFont.DemiBold, b.DISPLAY)
    b.text(p, "Clean junk. Undo anything.", x + 122 * u, y + 76 * u, 22 * u, b.MUTED)
    ty = y + 136 * u
    tile = (r.width() - 2 * pad - 2 * 20 * u) / 3
    tile = min(tile, r.bottom() - pad - 64 * u - ty)
    for i, bg in enumerate(("#ffffff", b.INK, b.BLUE)):
        t = QRectF(x + i * (tile + 20 * u), ty, tile, tile)
        p.setPen(QPen(QColor(255, 255, 255, 50), 1))
        p.setBrush(QColor(bg))
        p.drawRoundedRect(t, 16 * u, 16 * u)
        k = tile * 0.24
        p.drawImage(t.adjusted(k, k, -k, -k), b.logo())
    b.text(p, "Clear space: half the icon height. Never recolour, stretch or add effects to the icon.",
           x, ty + tile + 18 * u, 19 * u, b.MUTED, width=r.width() - 2 * pad)

    # colour: 3x3 swatches with name + hex
    r = cards["COLOUR"]
    sw_w = (r.width() - 2 * pad) / 3
    sz = 108 * u
    first = r.top() + pad + 40 * u
    step = (r.bottom() - pad - sz - first) / 2  # three rows spread over the card height
    for i, (name, hexv) in enumerate(b.PALETTE):
        x = r.left() + pad + (i % 3) * sw_w
        y = first + (i // 3) * step
        p.setPen(QPen(QColor(255, 255, 255, 70), 1.5))  # outline keeps the dark swatches visible
        p.setBrush(QColor(hexv))
        p.drawRoundedRect(QRectF(x, y, sz, sz), 14 * u, 14 * u)
        b.text(p, name, x + sz + 16 * u, y + 26 * u, 22 * u, b.WHITE, QFont.DemiBold)
        b.text(p, hexv.upper(), x + sz + 16 * u, y + 58 * u, 18 * u, b.MUTED, family="Consolas")

    # type
    r = cards["TYPE"]
    x, y, tw = r.left() + pad, r.top() + pad + 30 * u, r.width() - 2 * pad
    y += b.text(p, "Aa  Segoe UI Variable", x, y, 52 * u, b.WHITE, QFont.DemiBold, b.DISPLAY, width=tw)
    y += b.text(p, "Display · headlines · Semibold or Bold", x, y + 4 * u, 20 * u, b.MUTED, width=tw) + 22 * u
    y += b.text(p, "Aa  Segoe UI", x, y, 34 * u, b.WHITE, width=tw)
    b.text(p, "Body copy, UI labels and captions · plain, short sentences", x, y + 4 * u, 20 * u, b.MUTED,
           width=tw)

    # voice
    r = cards["VOICE"]
    x, y, tw = r.left() + pad, r.top() + pad + 34 * u, r.width() - 2 * pad - 30 * u
    for s in ("Calm, not alarming: never use scare tactics.",
              "Modest: a junk cleaner with basic checks, never sold as an antivirus.",
              "Honest: say what is removed, and how to undo it.",
              "Short: one idea per line, plain words.",
              "Respectful: works next to the antivirus you already have."):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(b.CYAN))
        p.drawEllipse(QRectF(x, y + 11 * u, 8 * u, 8 * u))
        y += b.text(p, s, x + 24 * u, y, 22 * u, b.WHITE, width=tw) + 12 * u
    p.end()
    return img


def main():
    app = QApplication(sys.argv)  # noqa: F841 - fonts need a QGuiApplication
    save(wide(1920, 1080), "hero.png")
    save(wide(1280, 640), "social-preview.png")   # GitHub repo social preview size
    save(wide(1200, 630), "og-image.png")         # Open Graph / Twitter card size
    save(billboard(), "billboard.png")
    save(square(), "social-square.png")
    for (title, desc, color), name in zip(b.FEATURES, ("cleaner", "overview", "security", "quarantine")):
        save(feature(title, desc, color, name), f"feature-{title.lower()}.png")
    save(feature_grid(), "features.png")
    save(themes(), "themes.png")
    save(brand_sheet(), "brand-sheet.png")


if __name__ == "__main__":
    main()
