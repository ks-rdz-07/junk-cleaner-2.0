"""30-second product video, drawn frame by frame with QPainter and encoded by ffmpeg.
python marketing/video.py  ->  docs/media/junk-cleaner-30s.mp4, -square.mp4, preview.gif, poster.png"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import brand as b  # noqa: E402

FPS, LENGTH, FADE = 30, 30.0, 0.5
OUT = os.path.join(b.ROOT, "docs", "media")

# (start, end, kind, screenshot, zoom-to crop as fractions, title, subtitle)
SCENES = [
    (0.0, 3.6, "intro", None, None, "", ""),
    (3.6, 9.0, "screen", "overview", (0.16, 0.05, 0.84, 0.30), "Your PC at a glance",
     "Antivirus, firewall, disk space and recent activity in one calm view."),
    (9.0, 14.6, "screen", "cleaner", (0.39, 0.0, 0.61, 0.62), "Find the junk. Review every item.",
     "Temp files, caches, crash dumps and leftovers. Nothing goes without your OK."),
    (14.6, 20.2, "screen", "security", (0.16, 0.27, 0.84, 0.28), "Update apps in parallel",
     "Live progress on every row, plus basic checks: Microsoft's on-demand scanner and missing patches."),
    (20.2, 25.4, "screen", "quarantine", (0.16, 0.0, 0.83, 0.42), "Changed your mind? Restore it.",
     "Quarantine keeps cleaned files for 30 days, with a full history."),
    (25.4, 30.0, "outro", None, None, "", ""),
]


def lerp(a, b_, t):
    return a + (b_ - a) * t


def scene_intro(p, w, h, t, d):
    b.backdrop(p, w, h, "overview", blur_px=40, dim=0.86, t=t / d)
    u = min(w, h) / 1080
    s = 170 * u * (0.6 + 0.4 * b.ease(t / 0.8))
    p.setOpacity(b.ease(t / 0.6))
    p.drawImage(QRectF(w / 2 - s / 2, h * 0.30 - s / 2, s, s), b.logo())
    p.setOpacity(1)
    wt = b.text_width("Junk Cleaner", 96 * u, QFont.DemiBold, b.DISPLAY)
    b.text(p, "Junk Cleaner", w / 2 - wt / 2, h * 0.30 + 110 * u + 30 * u * (1 - b.ease((t - 0.4) / 0.6)), 96 * u,
           b.WHITE, QFont.DemiBold, b.DISPLAY, opacity=b.ease((t - 0.4) / 0.6))
    for i, word in enumerate(("Clean junk.", "Undo anything.", "Basic security checks built in.")):
        k = b.ease((t - 1.2 - i * 0.45) / 0.5)
        color = b.CYAN if i == 1 else (b.MUTED if i == 2 else b.WHITE)
        tw = b.text_width(word, 54 * u, QFont.DemiBold, b.DISPLAY)
        b.text(p, word, w / 2 - tw / 2, h * 0.62 + i * 72 * u + 20 * u * (1 - k), 54 * u, color, QFont.DemiBold,
               b.DISPLAY, opacity=k)


def scene_screen(p, w, h, t, d, name, zoom, title, sub):
    b.backdrop(p, w, h, name, blur_px=34, dim=0.82, t=t / d)
    u = min(w, h) / 1080
    img = b.shot(name)
    full = QRectF(0, 0, img.width(), img.height())
    zx, zy, zw, zh = zoom
    target = QRectF(zx * img.width(), zy * img.height(), zw * img.width(), zh * img.height())
    square = w / h < 1.3
    if square:   # caption on top, window below
        cap_x, cap_y, cap_w = 70 * u, 90 * u, w - 140 * u
        win = QRectF(70 * u, h * 0.38, w - 140 * u, (w - 140 * u) / 1.64)
    else:        # caption left, window right
        cap_x, cap_y, cap_w = 110 * u, h * 0.36, w * 0.30
        win = QRectF(w * 0.40, h * 0.14, w * 0.56, w * 0.56 / 1.64)
    k_in = b.ease(t / 0.9)
    win.translate((1 - k_in) * 140 * u, 0)
    # hold the full window, then zoom into the feature (keeps the window frame, animates the source rect)
    z = b.ease_io((t - 1.6) / (d - 2.4))
    src = QRectF(lerp(full.x(), target.x(), z), lerp(full.y(), target.y(), z),
                 lerp(full.width(), target.width(), z), lerp(full.height(), target.height(), z))
    # keep the window's aspect while zooming
    want = win.width() / (win.height() - 34 * win.width() / 1600)
    if src.width() / src.height() > want:
        src.setWidth(src.height() * want)
    else:
        src.setHeight(src.width() / want)
    p.setOpacity(k_in)
    b.window(p, img, win, 16 * u, src=src)
    p.setOpacity(1)
    k = b.ease((t - 0.3) / 0.7)
    th = b.text(p, title, cap_x, cap_y + 24 * u * (1 - k), 58 * u, b.WHITE, QFont.DemiBold, b.DISPLAY, width=cap_w,
                opacity=k)
    k2 = b.ease((t - 0.7) / 0.7)
    b.text(p, sub, cap_x, cap_y + th + 22 * u + 24 * u * (1 - k2), 28 * u, b.MUTED, width=cap_w, opacity=k2)


def scene_outro(p, w, h, t, d):
    b.backdrop(p, w, h, "cleaner", blur_px=40, dim=0.86, t=t / d)
    u = min(w, h) / 1080
    k = b.ease(t / 0.7)
    s = 140 * u
    p.setOpacity(k)
    p.drawImage(QRectF(w / 2 - s / 2, h * 0.22, s, s), b.logo())
    p.setOpacity(1)
    for text, size, color, y, delay, wt in (("Junk Cleaner", 88, b.WHITE, 0.22 + 0.17, 0.2, QFont.DemiBold),
                                            ("Free & open source  ·  Windows & Linux", 34, b.MUTED, 0.53, 0.5,
                                             QFont.Normal),
                                            ("Beta  ·  junk cleaner with basic security checks", 34, b.CYAN, 0.62,
                                             0.8, QFont.DemiBold)):
        kk = b.ease((t - delay) / 0.6)
        tw = b.text_width(text, size * u, wt, b.DISPLAY)
        b.text(p, text, w / 2 - tw / 2, h * y + 18 * u * (1 - kk), size * u, color, wt, b.DISPLAY, opacity=kk)
    kk = b.ease((t - 1.2) / 0.6)
    p.setOpacity(kk)
    pills = (("Beta", b.AMBER), ("Apache-2.0", b.BLUE), ("No telemetry", b.VIOLET), ("Restorable cleanups", b.GREEN))
    total = sum(b.text_width(s_, 22 * u, QFont.DemiBold) + 22 * u * 1.6 for s_, _ in pills) + 2 * 16 * u
    x = w / 2 - total / 2
    for s_, c in pills:
        x += b.pill(p, s_, x, h * 0.74, 22 * u, c) + 16 * u
    p.setOpacity(1)


def render_scene(scene, w, h, t):
    start, end, kind, name, zoom, title, sub = scene
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
    lt, d = t - start, end - start
    if kind == "intro":
        scene_intro(p, w, h, lt, d)
    elif kind == "outro":
        scene_outro(p, w, h, lt, d)
    else:
        scene_screen(p, w, h, lt, d, name, zoom, title, sub)
    p.end()
    return img


def frame(w, h, t):
    """Current scene, cross-faded into the next one during the last FADE seconds."""
    i = next(n for n, s in enumerate(SCENES) if s[0] <= t < s[1] or n == len(SCENES) - 1)
    img = render_scene(SCENES[i], w, h, t)
    end = SCENES[i][1]
    if i + 1 < len(SCENES) and t > end - FADE:
        nxt = render_scene(SCENES[i + 1], w, h, t + FADE)  # next scene starts as the fade begins
        p = QPainter(img)
        p.setOpacity((t - (end - FADE)) / FADE)
        p.drawImage(0, 0, nxt)
        p.end()
    if t > LENGTH - 0.6:  # fade to black at the very end
        p = QPainter(img)
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, int(255 * (t - (LENGTH - 0.6)) / 0.6)))
        p.end()
    return img.convertToFormat(QImage.Format_ARGB32)


def encode(path, w, h):
    os.makedirs(OUT, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{w}x{h}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(LENGTH * FPS)
    for f in range(n):
        img = frame(w, h, f / FPS)
        proc.stdin.write(bytes(img.constBits())[: w * h * 4])
        if f % 150 == 0:
            print(f"{os.path.basename(path)}: {f * 100 // n}%", flush=True)
    proc.stdin.close()
    if proc.wait():
        raise SystemExit("ffmpeg failed")
    print("wrote", os.path.relpath(path, b.ROOT))


def main():
    app = QApplication(sys.argv)  # noqa: F841 - fonts need a QGuiApplication
    wide = os.path.join(OUT, "junk-cleaner-30s.mp4")
    encode(wide, 1920, 1080)
    encode(os.path.join(OUT, "junk-cleaner-30s-square.mp4"), 1080, 1080)
    frame(1920, 1080, 6.5).save(os.path.join(OUT, "poster.png"))
    # lightweight autoplaying preview for the README (GitHub won't inline-play repo-hosted mp4)
    gif = os.path.join(OUT, "preview.gif")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wide, "-vf",
                    "fps=10,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];"
                    "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle", gif], check=True)
    print("wrote", os.path.relpath(gif, b.ROOT))


if __name__ == "__main__":
    main()
