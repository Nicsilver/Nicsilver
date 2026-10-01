"""Generates the SVG graphics in assets/ used by the profile README.

Run: python tools/build.py   (needs Pillow + fonttools[woff] + brotli)
"""
import base64
import io
import random
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "src"
FONTS = ROOT / "tools" / "fonts"
OUT = ROOT / "assets"

FONT_FILES = {
    "Inter": ("Inter-Regular.ttf", 400),
    "InterMedium": ("Inter-Medium.ttf", 500),
    "InterSemi": ("Inter-SemiBold.ttf", 600),
    "InterDisplay": ("InterDisplay-Bold.ttf", 700),
    "InterDisplayX": ("InterDisplay-ExtraBold.ttf", 800),
}

BG = "#0d1016"
LINE = "#232833"
TEXT = "#eef1f6"
MUTED = "#98a1b3"
SPECTRUM = ["#7c5cff", "#2f8cff", "#14b88a", "#f5b53d", "#ff7a3d", "#ff4d6d"]


def b64(path):
    data = Path(path).read_bytes()
    mime = "image/png" if str(path).endswith(".png") else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def measure(text, family, size):
    # Pillow measures with the real font so chips and wrapped lines fit exactly.
    font = ImageFont.truetype(str(FONTS / FONT_FILES[family][0]), size)
    return font.getlength(text)


class Fonts:
    """Collects the glyphs each SVG uses, then embeds only those as woff2.

    SVGs shown through <img> can't fetch web fonts, so the font has to live
    inside the file. Subsetting keeps each card around 10-20 KB of font.
    """

    def __init__(self):
        self.used = {}

    def text(self, family, s):
        self.used.setdefault(family, set()).update(s)
        return s

    def css(self):
        rules = []
        for family, chars in self.used.items():
            file, weight = FONT_FILES[family]
            font = TTFont(FONTS / file)
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga", "calt", "tnum"]
            sub = subset.Subsetter(opts)
            sub.populate(text="".join(sorted(chars)) + " ")
            sub.subset(font)
            buf = io.BytesIO()
            font.flavor = "woff2"
            font.save(buf)
            data = base64.b64encode(buf.getvalue()).decode()
            rules.append(
                f"@font-face{{font-family:'{family}';font-weight:{weight};"
                f"src:url(data:font/woff2;base64,{data}) format('woff2');}}"
            )
        return "\n".join(rules)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def t(f, family, x, y, size, s, fill=TEXT, extra=""):
    f.text(family, s)
    return (
        f'<text x="{x}" y="{y}" font-family="{family}, Segoe UI, Helvetica, Arial, sans-serif" '
        f'font-size="{size}" fill="{fill}" {extra}>{esc(s)}</text>'
    )


def chip(f, x, y, label, color=None, size=15, h=32, family="InterMedium"):
    pad = 14
    dot = 14 if color else 0
    w = measure(label, family, size) + pad * 2 + dot
    parts = [f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="{h/2}" fill="#ffffff" fill-opacity="0.06" stroke="#ffffff" stroke-opacity="0.12"/>']
    if color:
        parts.append(f'<circle cx="{x + pad + 4}" cy="{y + h/2}" r="4" fill="{color}"/>')
    parts.append(t(f, family, x + pad + dot, y + h / 2 + size * 0.36, size, label, fill="#dfe4ee"))
    return "".join(parts), w


def icon(x, y, size, name, radius=0.23, extra=""):
    cid = f"clip-{name}-{x}-{y}"
    r = size * radius
    return (
        f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}"/></clipPath>'
        f'<image href="{b64(SRC / (name + ".png"))}" x="{x}" y="{y}" width="{size}" height="{size}" '
        f'clip-path="url(#{cid})" preserveAspectRatio="xMidYMid slice" {extra}/>'
        f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}" fill="none" stroke="#ffffff" stroke-opacity="0.10"/>'
    )


# Entrance animations are CSS with fill-mode "both" rather than SMIL, so a
# renderer without animation support still shows everything at rest.
BASE_CSS = """
.up{animation:up 1s cubic-bezier(.2,.8,.2,1) both}
.pop{transform-box:fill-box;transform-origin:center;animation:pop .9s cubic-bezier(.3,1.5,.5,1) both}
.rise{animation:rise 1.3s cubic-bezier(.2,.8,.2,1) both}
.grow{transform-box:fill-box;transform-origin:left center;animation:grow 1.2s cubic-bezier(.6,0,.2,1) both}
@keyframes up{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
@keyframes pop{from{opacity:0;transform:scale(.3) rotate(-12deg)}to{opacity:1;transform:none}}
@keyframes rise{from{opacity:0;transform:translateY(90px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleX(0)}to{transform:none}}
"""


def delay(s):
    return f'style="animation-delay:{s:.2f}s"'


def comet(w, h, r, stops, width=2.2, dur=6, count=2, begin=0):
    """Light streaks running around a rounded card border."""
    gid = f"comet{abs(hash((w, h, tuple(stops)))) % 10000}"
    grad = (
        f'<linearGradient id="{gid}" x1="0" x2="1" y1="0" y2="1">'
        + "".join(f'<stop offset="{i / max(1, len(stops) - 1):.2f}" stop-color="{c}"/>' for i, c in enumerate(stops))
        + '</linearGradient>'
    )
    parts = [grad]
    seg = 14 if count > 1 else 22
    gap = 100 / count - seg
    for blur, op, sw in [("url(#cometglow)", 0.9, width * 3), ("", 1, width)]:
        parts.append(
            f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="{r}" fill="none" stroke="url(#{gid})" '
            f'stroke-width="{sw}" stroke-linecap="round" pathLength="100" stroke-dasharray="{seg} {gap:.1f}" '
            f'opacity="{op}" {"filter=" + chr(34) + blur + chr(34) if blur else ""}>'
            f'<animate attributeName="stroke-dashoffset" values="100;0" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/></rect>'
        )
    return (
        '<filter id="cometglow" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="3"/></filter>'
        + "".join(parts)
    )


def svg(w, h, body, fonts, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{esc(label)}">\n<style>\n{fonts.css()}\n{BASE_CSS}</style>\n{body}\n</svg>\n'
    )


# ---------------------------------------------------------------- header

def header():
    f = Fonts()
    W, H = 1200, 360
    rnd = random.Random(7)
    out = [
        '<defs>',
        '<filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="60"/></filter>',
        '<filter id="spark" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="1.6"/></filter>',
        '<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#ffffff" fill-opacity="0.05"/></pattern>',
        f'<clipPath id="card"><rect width="{W}" height="{H}" rx="22"/></clipPath>',
        '<linearGradient id="spec" x1="0" x2="1">'
        + "".join(f'<stop offset="{i/(len(SPECTRUM)-1):.2f}" stop-color="{c}"/>' for i, c in enumerate(SPECTRUM))
        + '</linearGradient>',
        '</defs>',
        f'<g clip-path="url(#card)">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        f'<rect width="{W}" height="{H}" fill="url(#dots)"/>',
    ]
    # Slow drifting colour glows behind everything.
    for cx, cy, r, c, dx, dy, dur in [
        (980, 60, 170, "#7c5cff", -60, 40, 14),
        (1120, 320, 150, "#ff4d6d", -40, -30, 11),
        (760, 380, 140, "#2f8cff", 50, -20, 16),
        (120, -40, 120, "#14b88a", 40, 30, 18),
    ]:
        out.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}" opacity="0.38" filter="url(#blur)">'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;{dx} {dy};0 0" dur="{dur}s" repeatCount="indefinite"/></circle>'
        )
    # Sparks rising: "gnist" is Danish for spark.
    for i in range(34):
        x = rnd.uniform(20, W - 20)
        dur = rnd.uniform(5, 11)
        rise = rnd.uniform(120, 300)
        r = rnd.uniform(1.2, 2.6)
        c = rnd.choice(SPECTRUM + ["#ffffff"])
        begin = -rnd.uniform(0, dur)
        drift = rnd.uniform(-30, 30)
        out.append(
            f'<circle cx="{x:.0f}" cy="{H + 10}" r="{r:.1f}" fill="{c}" filter="url(#spark)">'
            f'<animate attributeName="cy" values="{H + 10};{H + 10 - rise:.0f}" dur="{dur:.1f}s" begin="{begin:.1f}s" repeatCount="indefinite"/>'
            f'<animate attributeName="cx" values="{x:.0f};{x + drift:.0f}" dur="{dur:.1f}s" begin="{begin:.1f}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;1;0.8;0" keyTimes="0;0.15;0.6;1" dur="{dur:.1f}s" begin="{begin:.1f}s" repeatCount="indefinite"/>'
            f'</circle>'
        )

    out.append(f'<g class="up" {delay(0.1)}>' + t(f, "InterMedium", 64, 104, 24, "Hi, I'm", fill=MUTED) + '</g>')
    # A spectrum band sweeps across the name every few seconds.
    out.append(
        '<linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="-500" x2="0" y1="0" y2="0">'
        '<stop offset="0" stop-color="#ffffff"/><stop offset="0.35" stop-color="#ffffff"/>'
        '<stop offset="0.45" stop-color="#f5b53d"/><stop offset="0.5" stop-color="#ff4d6d"/>'
        '<stop offset="0.55" stop-color="#7c5cff"/><stop offset="0.65" stop-color="#ffffff"/>'
        '<stop offset="1" stop-color="#ffffff"/>'
        '<animateTransform attributeName="gradientTransform" type="translate" values="0 0;0 0;1100 0" '
        'keyTimes="0;0.55;1" dur="7s" repeatCount="indefinite"/></linearGradient>'
    )
    out.append(f'<g class="up" {delay(0.25)}>' + t(f, "InterDisplayX", 62, 178, 72, "Nicolaj Jensen", fill="url(#shine)", extra='letter-spacing="-1.5"') + '</g>')

    # Typewriter line: "I build <word>" with the word typed, held, and erased in turn.
    prefix = "I build "
    size = 30
    y = 236
    out.append(f'<g class="up" {delay(0.45)}>' + t(f, "InterSemi", 64, y, size, prefix, fill="#c9d0dc") + '</g>')
    x0 = 64 + measure(prefix, "InterSemi", size)
    words = [
        ("Android apps.", "#14b88a"),
        ("TV remotes.", "#ff4d6d"),
        ("IDE plugins.", "#7c9bff"),
        ("party games.", "#f5b53d"),
        ("tools in Rust.", "#ff7a3d"),
        ("websites.", "#b18cff"),
    ]
    slot = 3.2
    total = slot * len(words)
    cursor_x = []
    for i, (word, color) in enumerate(words):
        widths, times = [0.0], [0.0]
        start = i * slot
        type_step = 0.07
        for k in range(1, len(word) + 1):
            times.append(start + k * type_step)
            widths.append(measure(word[:k], "InterSemi", size))
        hold_end = start + slot - 0.55
        for k in range(len(word) - 1, -1, -1):
            hold_end += 0.03
            times.append(hold_end)
            widths.append(measure(word[:k], "InterSemi", size))
        kt = ";".join(f"{tt / total:.4f}" for tt in times)
        vals = ";".join(f"{w:.1f}" for w in widths)
        cid = f"type{i}"
        out.append(
            f'<clipPath id="{cid}"><rect x="{x0:.1f}" y="{y - size}" height="{size + 12}" width="0">'
            f'<animate attributeName="width" values="{vals}" keyTimes="{kt}" calcMode="discrete" dur="{total}s" repeatCount="indefinite"/>'
            f'</rect></clipPath>'
        )
        out.append(f'<g clip-path="url(#{cid})">' + t(f, "InterSemi", x0, y, size, word, fill=color) + '</g>')
        cursor_x.append((times, widths))
    # One cursor that follows whichever word is currently being typed.
    times, xs = [], []
    for tm, wd in cursor_x:
        times += tm
        xs += wd
    pairs = sorted(set(zip(times, xs)), key=lambda p: p[0])
    dedup = []
    for tm, wd in pairs:
        if dedup and abs(dedup[-1][0] - tm) < 1e-6:
            dedup[-1] = (tm, wd)
        else:
            dedup.append((tm, wd))
    kt = ";".join(f"{tm / total:.4f}" for tm, _ in dedup)
    vals = ";".join(f"{x0 + wd + 3:.1f}" for _, wd in dedup)
    out.append(
        f'<rect x="{x0 + 3:.1f}" y="{y - size + 4}" width="3" height="{size + 2}" rx="1.5" fill="#eef1f6">'
        f'<animate attributeName="x" values="{vals}" keyTimes="{kt}" calcMode="discrete" dur="{total}s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1s" repeatCount="indefinite"/>'
        f'</rect>'
    )

    out.append(f'<rect class="grow" {delay(0.6)} x="64" y="272" width="120" height="4" rx="2" fill="url(#spec)"/>')
    out.append(f'<g class="up" {delay(0.8)}>' + t(f, "InterMedium", 64, 312, 18, "Full-stack dev at Brunata   ·   Gnist Studio   ·   Denmark", fill=MUTED) + '</g>')

    # Floating app icons on the right.
    floats = [
        ("lgpower", 856, 54, 104, 5.0, 10),
        ("flutster", 990, 96, 84, 6.0, 8),
        ("roam", 1090, 30, 70, 5.5, 9),
        ("glimt", 1086, 196, 78, 6.5, 10),
        ("jumper", 960, 214, 66, 4.8, 8),
        ("pcio", 820, 196, 70, 6.2, 9),
        ("claude-sessions", 1112, 126, 48, 5.2, 7),
    ]
    for i, (name, x, y0, s, dur, amp) in enumerate(floats):
        out.append(
            f'<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -{amp};0 0" '
            f'dur="{dur}s" begin="-{i * 0.7:.1f}s" repeatCount="indefinite" calcMode="spline" keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>'
            f'<g class="pop" {delay(0.5 + i * 0.12)}>'
            f'<rect x="{x}" y="{y0 + 10}" width="{s}" height="{s}" rx="{s * 0.23}" fill="#000" opacity="0.45" filter="url(#spark)"/>'
            + icon(x, y0, s, name)
            + '</g></g>'
        )

    out.append('</g>')
    out.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="22" fill="none" stroke="{LINE}"/>')
    out.append(comet(W, H, 22, SPECTRUM, dur=9))
    return svg(W, H, "\n".join(out), f, "Hi, I'm Nicolaj Jensen. I build Android apps, TV remotes, IDE plugins, party games and tools in Rust.")


# ---------------------------------------------------------------- LG Power hero

def hero():
    f = Fonts()
    W, H = 1200, 500
    out = [
        '<defs>',
        '<filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="70"/></filter>',
        '<filter id="shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#000" flood-opacity="0.55"/></filter>',
        f'<clipPath id="card"><rect width="{W}" height="{H}" rx="22"/></clipPath>',
        '</defs>',
        '<g clip-path="url(#card)">',
        f'<rect width="{W}" height="{H}" fill="#0c0b12"/>',
    ]
    # Red-to-blue glow from the LG Power store banner.
    for cx, cy, r, c, op, dur in [
        (180, 60, 240, "#d8343c", 0.55, 9),
        (700, 470, 260, "#6a2fb8", 0.45, 12),
        (1100, 120, 260, "#2846c8", 0.6, 10),
    ]:
        out.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}" opacity="{op}" filter="url(#blur)">'
            f'<animate attributeName="opacity" values="{op};{op * 0.6:.2f};{op}" dur="{dur}s" repeatCount="indefinite"/></circle>'
        )

    label, lw = chip(f, 64, 44, "FEATURED PROJECT", color="#ff4d6d", size=13, h=28, family="InterSemi")
    out.append(f'<g class="up">{label}<circle cx="82" cy="58" r="4" fill="#ff4d6d">'
               '<animate attributeName="r" values="4;9;4" dur="1.6s" repeatCount="indefinite"/>'
               '<animate attributeName="opacity" values="0.8;0;0.8" dur="1.6s" repeatCount="indefinite"/></circle></g>')
    # IR pulses leaving the remote icon, like it's switching the TV on.
    for i in range(3):
        out.append(
            f'<path d="M 166 131 a 18 18 0 0 1 0 30" fill="none" stroke="#ff4d6d" stroke-width="3" stroke-linecap="round" opacity="0">'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;18 0" dur="2.4s" begin="{i * 0.8}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;0.9;0" dur="2.4s" begin="{i * 0.8}s" repeatCount="indefinite"/></path>'
        )
    out.append(f'<g class="pop" {delay(0.15)}>' + icon(64, 100, 92, "lgpower") + '</g>')
    out.append(f'<g class="up" {delay(0.3)}>' + t(f, "InterDisplayX", 200, 152, 58, "LG Power", extra='letter-spacing="-1"') + '</g>')
    out.append(f'<g class="up" {delay(0.4)}>' + t(f, "InterMedium", 202, 186, 22, "A remote for LG webOS TVs", fill="#c9cfdb") + '</g>')

    para = [
        "Native Android app in Kotlin. Controls the TV over",
        "Wi-Fi through the webOS API, and powers it on with",
        "the phone's IR blaster when the network can't. Touchpad,",
        "keyboard, media keys, widgets. No ads, open source.",
    ]
    for i, line in enumerate(para):
        out.append(f'<g class="up" {delay(0.5 + i * 0.08)}>' + t(f, "Inter", 64, 250 + i * 30, 19, line, fill="#d5dae4") + '</g>')

    x = 64
    for i, (name, color) in enumerate([("Kotlin", "#a97bff"), ("Android", "#3ddc84"), ("webOS API", "#ff4d6d"), ("IR blaster", "#f5b53d"), ("iOS port in Flutter", "#2f8cff")]):
        c, w = chip(f, x, 384, name, color=color)
        out.append(f'<g class="pop" {delay(0.9 + i * 0.1)}>{c}</g>')
        x += w + 10

    out.append(f'<g class="up" {delay(1.4)}>' + t(f, "InterMedium", 64, 456, 16, "Free on Google Play   ·   github.com/Nicsilver/LGPower", fill="#9aa2b4") + '</g>')

    # Three store screenshots fanned out, each floating gently.
    shots = [
        ("lgpower-shot2.jpg", 720, 70, 214, -7, 6.5),
        ("lgpower-shot3.jpg", 960, 70, 214, 7, 7.0),
        ("lgpower-shot1.jpg", 832, 44, 240, 0, 5.5),
    ]
    for i, (file, sx, sy, sw, rot, dur) in enumerate(shots):
        sh = sw * 1280 / 720
        cx, cy = sx + sw / 2, sy + sh / 2
        cid = f"shot{i}"
        out.append(
            f'<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -10;0 0" dur="{dur}s" '
            f'begin="-{i * 1.3:.1f}s" repeatCount="indefinite" calcMode="spline" keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>'
            f'<g class="rise" {delay(0.3 + i * 0.25)}><g transform="rotate({rot} {cx:.0f} {cy:.0f})">'
            f'<clipPath id="{cid}"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh:.0f}" rx="18"/></clipPath>'
            f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh:.0f}" rx="18" fill="#000" filter="url(#shadow)"/>'
            f'<image href="{b64(SRC / file)}" x="{sx}" y="{sy}" width="{sw}" height="{sh:.0f}" clip-path="url(#{cid})" preserveAspectRatio="xMidYMid slice"/>'
            f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh:.0f}" rx="18" fill="none" stroke="#ffffff" stroke-opacity="0.14"/>'
            f'</g></g></g>'
        )

    out.append('</g>')
    out.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="22" fill="none" stroke="#2a2433"/>')
    out.append(comet(W, H, 22, ["#ff4d6d", "#b14dff", "#2f6bff"], dur=7))
    return svg(W, H, "\n".join(out), f, "LG Power: a remote for LG webOS TVs. Native Android app in Kotlin, free on Google Play.")


# ---------------------------------------------------------------- project cards

PROJECTS = [
    ("flutster", "Flutster", "#f5b53d", "Google Play",
     ["Music-timeline party game. Scan a card,", "the song plays, guess the year."],
     [("Flutter", "#2f8cff"), ("Dart", "#14b8c4"), ("Web card maker", "#ff4d6d")]),
    ("roam", "Roam", "#ff8a3d", "Google Play",
     ["GPS speedometer whose readout keeps", "moving, so your OLED never burns in."],
     [("Kotlin", "#a97bff"), ("Android", "#3ddc84")]),
    ("pcio", "PCIO", "#aab4c4", "Google Play",
     ["Your phone as a wireless mouse and", "keyboard for your PC, over local Wi-Fi."],
     [("Java", "#f89820"), ("Android", "#3ddc84"), ("Desktop server", "#aab4c4")]),
    ("glimt", "Glimt", "#ffc93c", "Windows",
     ["Instant area screenshots and MP4/GIF", "recording. One portable exe, pure Rust."],
     [("Rust", "#ff7a3d"), ("Win32", "#2f8cff")]),
    ("jumper", "Jumper", "#7da2fe", "JetBrains Marketplace",
     ["IDE plugin that jumps the caret several", "lines with a single keybind."],
     [("Kotlin", "#a97bff"), ("IntelliJ Platform", "#ff4d6d")]),
    ("claude-sessions", "Claude Sessions", "#32c75a", "Windows + macOS",
     ["Live dashboard of every Claude Code", "session. See who needs you, jump there."],
     [("Rust", "#ff7a3d"), ("Tauri", "#ffc131"), ("IntelliJ plugin", "#7da2fe")]),
]


def card(key, name, accent, where, desc, chips):
    f = Fonts()
    W, H = 600, 220
    out = [
        '<defs>',
        f'<radialGradient id="glow" cx="1" cy="0" r="1"><stop offset="0" stop-color="{accent}" stop-opacity="0.30"/><stop offset="0.7" stop-color="{accent}" stop-opacity="0"/></radialGradient>',
        f'<linearGradient id="bar" x1="0" x2="1"><stop offset="0" stop-color="{accent}" stop-opacity="0"/><stop offset="0.5" stop-color="{accent}"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient>',
        f'<clipPath id="card"><rect width="{W}" height="{H}" rx="18"/></clipPath>',
        '</defs>',
        '<g clip-path="url(#card)">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        f'<rect width="{W}" height="{H}" fill="url(#glow)"><animate attributeName="opacity" values="1;0.55;1" dur="6s" repeatCount="indefinite"/></rect>',
        # A soft light that sweeps along the top edge.
        f'<rect x="-220" y="0" width="220" height="2" fill="url(#bar)"><animate attributeName="x" values="-220;{W}" dur="5s" repeatCount="indefinite"/></rect>',
    ]
    out.append(f'<g class="pop" {delay(0.1)}>' + icon(28, 30, 84, key) + '</g>')
    out.append(f'<g class="up" {delay(0.2)}>' + t(f, "InterDisplay", 134, 66, 30, name, extra='letter-spacing="-0.4"') + '</g>')
    pill_size = 13
    pw = measure(where, "InterSemi", pill_size) + 24
    out.append(f'<g class="pop" {delay(0.5)}><rect x="{W - 28 - pw:.1f}" y="30" width="{pw:.1f}" height="26" rx="13" fill="{accent}" fill-opacity="0.14" stroke="{accent}" stroke-opacity="0.45"/>'
               + t(f, "InterSemi", W - 28 - pw + 12, 47.5, pill_size, where, fill=accent) + '</g>')
    for i, line in enumerate(desc):
        out.append(f'<g class="up" {delay(0.3 + i * 0.08)}>' + t(f, "Inter", 134, 100 + i * 26, 17.5, line, fill="#c4cbd8") + '</g>')
    x = 134
    for i, (label, color) in enumerate(chips):
        c, w = chip(f, x, 160, label, color=color, size=14, h=30)
        out.append(f'<g class="pop" {delay(0.55 + i * 0.1)}>{c}</g>')
        x += w + 8
    out.append('</g>')
    out.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="18" fill="none" stroke="{LINE}"/>')
    out.append(comet(W, H, 18, [accent, "#ffffff", accent], width=1.8, dur=8, count=1, begin=-[p[0] for p in PROJECTS].index(key) * 1.3))
    return svg(W, H, "\n".join(out), f, f"{name}: {' '.join(desc)}")


SECTIONS = [
    ("featured", "01", "FEATURED", "What I'm building right now"),
    ("shipped", "02", "SHIPPED", "More things I've made"),
    ("stack", "03", "STACK", "Tools of the trade"),
    ("activity", "04", "ACTIVITY", "The snake eats my commits"),
]


def section(num, kicker, title, dark):
    # Transparent background, so it needs a light and a dark variant.
    ink = TEXT if dark else "#1f2328"
    rule = "#ffffff" if dark else "#000000"
    f = Fonts()
    W, H = 1200, 120
    out = [
        '<defs><linearGradient id="spec" x1="0" x2="1">'
        + "".join(f'<stop offset="{i/(len(SPECTRUM)-1):.2f}" stop-color="{c}"/>' for i, c in enumerate(SPECTRUM))
        + '</linearGradient>'
        '<linearGradient id="flow" gradientUnits="userSpaceOnUse" x1="0" x2="600" spreadMethod="repeat">'
        + "".join(f'<stop offset="{i/len(SPECTRUM):.2f}" stop-color="{c}"/>' for i, c in enumerate(SPECTRUM + [SPECTRUM[0]]))
        + '<animateTransform attributeName="gradientTransform" type="translate" values="0 0;600 0" dur="6s" repeatCount="indefinite"/>'
        '</linearGradient>'
        '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4"/></filter></defs>',
    ]
    # Four-point spark that spins slowly and pulses.
    star = "M 0 -16 C 2 -4 4 -2 16 0 C 4 2 2 4 0 16 C -2 4 -4 2 -16 0 C -4 -2 -2 -4 0 -16 Z"
    out.append(
        f'<g transform="translate(30 66)"><g class="pop">'
        f'<path d="{star}" fill="url(#flow)" filter="url(#glow)" opacity="0.8"/><path d="{star}" fill="url(#flow)">'
        f'<animateTransform attributeName="transform" type="rotate" values="0;90" dur="4s" repeatCount="indefinite"/></path>'
        f'</g></g>'
    )
    out.append(f'<g class="up" {delay(0.1)}>' + t(f, "InterSemi", 62, 44, 15, f"{num}  /  {kicker}", fill="url(#flow)", extra='letter-spacing="3"') + '</g>')
    out.append(f'<g class="up" {delay(0.2)}>' + t(f, "InterDisplayX", 60, 86, 40, title, fill=ink, extra='letter-spacing="-0.8"') + '</g>')
    tw = measure(title, "InterDisplayX", 40) - 0.8 * len(title)
    out.append(f'<rect class="grow" {delay(0.4)} x="62" y="104" width="{tw:.0f}" height="4" rx="2" fill="url(#flow)"/>')
    out.append(f'<rect class="grow" {delay(0.7)} x="{62 + tw + 14:.0f}" y="105.5" width="{W - 62 - tw - 14:.0f}" height="1" fill="{rule}" fill-opacity="0.10"/>')
    return svg(W, H, "\n".join(out), f, title)


def main():
    OUT.mkdir(exist_ok=True)
    files = {"header.svg": header(), "lgpower.svg": hero()}
    for slug, num, kicker, title in SECTIONS:
        files[f"section-{slug}.svg"] = section(num, kicker, title, dark=False)
        files[f"section-{slug}-dark.svg"] = section(num, kicker, title, dark=True)
    for p in PROJECTS:
        files[f"card-{p[0]}.svg"] = card(*p)
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
        print(f"{name:28} {len(content.encode()) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
