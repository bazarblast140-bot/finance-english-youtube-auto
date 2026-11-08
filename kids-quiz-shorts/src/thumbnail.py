"""Custom Shorts / IG / FB cover (1080x1920) — naye post ke liye.

Poora sawaal, bold Devanagari, 2-4 lines, auto font. Grid crop
(centre 1080x1350) ke andar text. Har sawaal ka apna background rang,
ek simple topic icon. Jawab, option/answer ke number, aur
parenthetical saal (Panipat 1526) cover par nahi aate.

Naye build `make()` se thumbnail.jpg mp4 ke paas likhte hain.
Purani video / backfill yahan se nahi chalti.
"""
import argparse
import json
import re
import zlib
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config as C

# IG/FB grid 4:5 = centre 1080x1350 of the 1080x1920 file.
GRID_W, GRID_H = 1080, 1350
SAFE_TOP = (C.H - GRID_H) // 2          # 285
SAFE_BOTTOM = SAFE_TOP + GRID_H         # 1635
SAFE_LEFT, SAFE_RIGHT = 48, C.W - 48

# Text block sits under the icon and above the pill, all inside the crop.
TEXT_AREA = (80, 590, C.W - 80, 1410)
MAX_FONT = 150
MIN_LINES, MAX_LINES = 2, 4
WHITE = (255, 255, 255)
PILL_BG = (253, 208, 64)
PILL_FG = (32, 22, 48)

# Jewel tones — flat colour, not one shared purple blur. Channels stay
# dark enough that white Devanagari clears WCAG-style contrast.
PALETTE = [
    (14, 112, 124),   # teal
    (16, 104, 72),    # forest
    (128, 36, 68),    # wine
    (24, 58, 128),    # navy
    (140, 84, 22),    # amber
    (72, 36, 138),    # purple
    (148, 64, 28),    # rust
    (18, 86, 102),    # ocean
    (96, 36, 112),    # plum
    (20, 108, 64),    # green
    (122, 42, 40),    # brick
    (28, 64, 108),    # slate
    (116, 62, 18),    # copper
    (36, 48, 124),    # indigo
    (112, 28, 56),    # maroon
    (12, 96, 108),    # deep teal
]

_PUNCT = " ?？!।,.，、'\"‘’“”()[]{}—–-:;؛…«»"
_NUM_RE = re.compile(r"[0-9०-९]+")
_PAREN_YEAR_RE = re.compile(
    r"[\(\[（]\s*[0-9०-९]{3,4}\s*(?:ई\.?|ईसवी|CE|AD|BC|BCE)?\s*[\)\]）]"
)
_WORD_RE_TMPL = r"(?<![\w\u0900-\u097F]){key}(?![\w\u0900-\u097F])"
_ASC = "0123456789"
_DEV = "०१२३४५६७८९"
_TO_ASC = str.maketrans(_DEV, _ASC)
_TO_DEV = str.maketrans(_ASC, _DEV)

# Longer keys win. Matched on the question only (subject is the fallback).
ICON_KEYWORDS = [
    ("रेडियोधर्मिता", "atom"),
    ("राष्ट्रगान", "music"),
    ("संविधान", "book"),
    ("जलप्रपात", "river"),
    ("चमगादड़", "bat"),
    ("सौरमंडल", "planet"),
    ("अंतरिक्ष", "planet"),
    ("सूर्योदय", "sun"),
    ("बल्लेबाज़", "cricket"),
    ("बल्लेबाज", "cricket"),
    ("रिज़र्व", "bank"),
    ("पुरस्कार", "medal"),
    ("कंप्यूटर", "computer"),
    ("हाइड्रोजन", "flask"),
    ("ऑक्सीजन", "flask"),
    ("उँगलियों", "fingerprint"),
    ("उंगलियों", "fingerprint"),
    ("पानीपत", "swords"),
    ("क्रिकेट", "cricket"),
    ("प्रारूप", "book"),
    ("किताब", "book"),
    ("पुस्तक", "book"),
    ("तलवार", "swords"),
    ("युद्ध", "swords"),
    ("टेनिस", "tennis"),
    ("बादशाह", "cards"),
    ("तापमान", "drop"),
    ("समुद्र", "drop"),
    ("झरना", "river"),
    ("उपग्रह", "rocket"),
    ("रॉकेट", "rocket"),
    ("चंद्र", "moon"),
    ("चन्द्र", "moon"),
    ("चाँद", "moon"),
    ("सूरज", "sun"),
    ("सूर्य", "sun"),
    ("बिजली", "lightning"),
    ("नोबेल", "medal"),
    ("पदक", "medal"),
    ("आवाज़", "sound"),
    ("ध्वनि", "sound"),
    ("खंडहर", "ruins"),
    ("पहाड़", "mountain"),
    ("पर्वत", "mountain"),
    ("झंडा", "flag"),
    ("ध्वज", "flag"),
    ("तिरंगा", "flag"),
    ("पहेली", "puzzle"),
    ("शार्क", "fish"),
    ("मछली", "fish"),
    ("व्हेल", "fish"),
    ("मकड़ी", "spider"),
    ("नदी", "river"),
    ("झील", "river"),
    ("पानी", "drop"),
    ("बैंक", "bank"),
    ("रुपये", "bank"),
    ("रुपया", "bank"),
    ("घड़ी", "clock"),
    ("क्यूब", "cube"),
    ("गैस", "flask"),
    ("शरीर", "body"),
    ("हड्डी", "body"),
    ("खून", "body"),
    ("ग्रहण", "moon"),
    ("ग्रह", "planet"),
    ("ताश", "cards"),
    ("पुल", "bridge"),
    ("किला", "ruins"),
    ("देश", "globe"),
    ("पृथ्वी", "globe"),
    ("नक्शा", "globe"),
    ("दुनिया", "globe"),
]
SUBJECT_ICON = {
    "पहेली": "puzzle",
    "विज्ञान": "atom",
    "भारत": "flag",
    "दुनिया": "globe",
    "सामान्य ज्ञान": "book",
}


def _bare(token):
    return str(token).strip(_PUNCT)


def _ascii_digits(text):
    return str(text).translate(_TO_ASC)


def _dev_digits(text):
    return str(text).translate(_TO_DEV)


def _answer(q):
    opts = q.get("opts") or []
    idx = q.get("ans")
    if isinstance(idx, int) and 0 <= idx < len(opts):
        return str(opts[idx]).strip()
    return ""


def _answer_tokens(q):
    ans = _answer(q)
    if len(_bare(ans)) <= 1:
        return []
    return [_bare(t) for t in ans.split() if _bare(t)]


def forbidden_numbers(q):
    """Years/numbers that appear in the answer or any option."""
    blobs = [str(o) for o in (q.get("opts") or [])]
    ans = _answer(q)
    if ans:
        blobs.append(ans)
    found = set()
    for blob in blobs:
        found.update(_NUM_RE.findall(_ascii_digits(blob)))
    return found


def parenthetical_years(text):
    years = set()
    for m in _PAREN_YEAR_RE.findall(str(text or "")):
        years.update(_NUM_RE.findall(_ascii_digits(m)))
    return years


def _contains_number(text, number):
    forms = {str(number), _dev_digits(str(number))}
    for form in forms:
        if re.search(rf"(?<![0-9०-९]){re.escape(form)}(?![0-9०-९])", str(text)):
            return True
    return False


def _contains_answer_phrase(text, q):
    toks = _answer_tokens(q)
    if not toks:
        return False
    bare = [_bare(w) for w in str(text).split()]
    n = len(toks)
    return any(bare[i:i + n] == toks for i in range(len(bare) - n + 1))


def leaks_answer(text, q):
    """True if cover text still shows the answer, an answer/option number, or a parenthetical year."""
    if _contains_answer_phrase(text, q):
        return True
    for n in forbidden_numbers(q) | parenthetical_years(q.get("q", "")):
        if _contains_number(text, n):
            return True
    return False


def _strip_numbers(text, numbers):
    for n in sorted(numbers, key=len, reverse=True):
        if not n:
            continue
        for form in {str(n), _dev_digits(str(n))}:
            text = re.sub(rf"(?<![0-9०-९]){re.escape(form)}(?![0-9०-९])", " ", text)
    return text


def _strip_answer_phrase(text, q):
    toks = _answer_tokens(q)
    if not toks:
        return text
    words = text.split()
    bare = [_bare(w) for w in words]
    n = len(toks)
    drop = set()
    i = 0
    while i <= len(words) - n:
        if bare[i:i + n] == toks and any(len(t) > 1 for t in toks):
            drop.update(range(i, i + n))
            i += n
        else:
            i += 1
    if not drop:
        return text
    return " ".join(w for i, w in enumerate(words) if i not in drop)


def cover_text(q):
    """Full question for the cover. Answer and spoiler numbers are removed, nothing else."""
    raw = str(q.get("q") or "").strip()
    text = _PAREN_YEAR_RE.sub(" ", raw)
    text = _strip_numbers(text, forbidden_numbers(q))
    text = _strip_answer_phrase(text, q)
    text = re.sub(r"\(\s*\)", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([?？।,])", r"\1", text)
    had_qmark = "?" in raw or "？" in raw
    if had_qmark and "?" not in text and "？" not in text:
        text = text.rstrip(" ।.,—–-") + "?"
    if not any(_bare(w) for w in text.split()):
        text = "सवाल पहचानिए?"
    return text


def hook_text(q):
    """Cover par jo text jaata hai — poora sawaal (purana 2-5 shabd wala hook nahi)."""
    return cover_text(q)


def _key(q):
    return str(q.get("id") or q.get("q") or "").encode("utf-8")


def background_color(q):
    return PALETTE[zlib.crc32(_key(q)) % len(PALETTE)]


def _shift(rgb, amount, cap=188):
    return tuple(min(cap, max(0, c + amount)) for c in rgb)


def topic_icon(q):
    blob = f"{q.get('q', '')} {q.get('topic', '')}"
    for key, name in sorted(ICON_KEYWORDS, key=lambda kv: len(kv[0]), reverse=True):
        if re.search(_WORD_RE_TMPL.format(key=re.escape(key)), blob):
            return name
    return SUBJECT_ICON.get(q.get("sub"), "quiz")


# Noto Sans Devanagari has no Latin letters (they come out as empty boxes).
# English words in the question — "(radioactivity)", "QUIZ" — use a Latin bold face.
_LATIN_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
_font_cache = {}
_latin_file = None


def _latin_path():
    global _latin_file
    if _latin_file:
        return _latin_file
    for p in _LATIN_CANDIDATES:
        if Path(p).exists():
            _latin_file = p
            return p
    raise FileNotFoundError("Latin bold font nahi mila (Noto Sans Bold / Liberation / DejaVu)")


def latin_font(size):
    key = ("lat", int(size))
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(_latin_path(), int(size))
    return _font_cache[key]


def dev_font(size):
    import render
    return render.F(int(size), bold=True)


def font_for(kind, size):
    return latin_font(size) if kind == "lat" else dev_font(size)


def _base_script(ch):
    o = ord(ch)
    if 0x0900 <= o <= 0x097F or ch in "\u200c\u200d":
        return "dev"
    if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
        return "lat"
    return None


def _runs(text):
    """Split into Devanagari vs Latin runs. Neutral marks stick to their word."""
    if not text:
        return []
    bases = [_base_script(ch) for ch in text]
    resolved = []
    last = "dev"
    for b in bases:
        if b:
            last = b
        resolved.append(last)
    nxt = None
    for i in range(len(text) - 1, -1, -1):
        if bases[i]:
            nxt = bases[i]
        elif text[i] in "([{'\"“‘" and nxt:
            resolved[i] = nxt
    runs = []
    for ch, kind in zip(text, resolved):
        if runs and runs[-1][0] == kind:
            runs[-1] = (kind, runs[-1][1] + ch)
        else:
            runs.append((kind, ch))
    return runs


def _line_metrics(line, size):
    """Ink box of one line. Origin is the Devanagari em-box top-left."""
    dev = dev_font(size)
    dev_asc, _ = dev.getmetrics()
    runs = _runs(line)
    x = 0.0
    inks = []
    placed = []
    for kind, seg in runs:
        font = font_for(kind, size)
        asc, _ = font.getmetrics()
        y_off = dev_asc - asc
        b = font.getbbox(seg)
        inks.append((x + b[0], y_off + b[1], x + b[2], y_off + b[3]))
        placed.append((kind, seg, x, y_off, font))
        x += font.getlength(seg)
    if not inks:
        return None
    left = min(i[0] for i in inks)
    top = min(i[1] for i in inks)
    right = max(i[2] for i in inks)
    bot = max(i[3] for i in inks)
    return {
        "runs": placed,
        "ink": (left, top, right, bot),
        "width": right - left,
        "height": bot - top,
    }


def _ink_w(text, size):
    m = _line_metrics(text, size)
    return 0 if m is None else m["width"]


def _wrap(text, size, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if _ink_w(trial, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _measure(lines, size, max_w, max_h):
    if not lines:
        return None
    metrics = [_line_metrics(ln, size) for ln in lines]
    if any(m is None or m["width"] > max_w + 0.5 for m in metrics):
        return None
    gap = max(12, int(size * 0.16))
    heights = [m["height"] for m in metrics]
    total_h = sum(heights) + gap * (len(lines) - 1)
    if total_h > max_h:
        return None
    return {"lines": metrics, "gap": gap, "heights": heights, "total_h": total_h}


def _fit(text, area):
    x0, y0, x1, y1 = area
    max_w, max_h = x1 - x0, y1 - y0
    best = None
    size = MAX_FONT
    while size >= 8:
        lines = _wrap(text, size, max_w)
        metrics = _measure(lines, size, max_w, max_h)
        if metrics is not None:
            pack = (lines, size, metrics)
            n = len(lines)
            if best is None:
                best = pack
            if MIN_LINES <= n <= MAX_LINES or n < MIN_LINES:
                return pack
        size -= 2
    if best is None:
        raise RuntimeError("cover text did not fit without dropping words")
    return best


def _place(lines, metrics, area):
    x0, y0, x1, y1 = area
    max_w = x1 - x0
    gap = metrics["gap"]
    y = y0 + ((y1 - y0) - metrics["total_h"]) / 2
    positions, bounds = [], []
    for ln, m, h in zip(lines, metrics["lines"], metrics["heights"]):
        left, top, right, bot = m["ink"]
        # em-box origin so the ink is centered and its top sits at y
        draw_x = x0 + (max_w - (right - left)) / 2 - left
        draw_y = y - top
        positions.append((draw_x, draw_y))
        bounds.append((draw_x + left, y, draw_x + right, y + h))
        y += h + gap
    return positions, bounds


def _qmark_bbox(line, origin, size):
    x, draw_y = origin
    m = _line_metrics(line, size)
    if m is None:
        return None
    found = None
    for kind, seg, pen, y_off, font in m["runs"]:
        idx = max(seg.rfind("?"), seg.rfind("？"))
        if idx < 0:
            continue
        prefix = seg[:idx]
        pen_x = x + pen + (font.getlength(prefix) if prefix else 0)
        gb = font.getbbox(seg[idx])
        found = (pen_x + gb[0], draw_y + y_off + gb[1],
                 pen_x + gb[2], draw_y + y_off + gb[3])
    return found


def layout_cover(q):
    """Measure the cover. Does not write a file."""
    text = cover_text(q)
    lines, size, metrics = _fit(text, TEXT_AREA)
    positions, bounds = _place(lines, metrics, TEXT_AREA)
    qbox = None
    for ln, origin in zip(lines, positions):
        if "?" in ln or "？" in ln:
            qbox = _qmark_bbox(ln, origin, size)
    return {
        "text": text,
        "lines": lines,
        "font_size": size,
        "text_bounds": [tuple(round(v, 1) for v in b) for b in bounds],
        "qmark_bbox": None if qbox is None else tuple(round(v, 1) for v in qbox),
        "positions": positions,
        "bg": background_color(q),
        "icon": topic_icon(q),
    }


def _draw_line(draw, line, origin, size, fill):
    x, draw_y = origin
    m = _line_metrics(line, size)
    for kind, seg, pen, y_off, font in m["runs"]:
        draw.text((x + pen, draw_y + y_off), seg, font=font, fill=fill)


def _paint_arc(img, q, color):
    h = zlib.crc32(_key(q))
    accent = _shift(color, 42)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    cx = 160 + (h % 760)
    cy = 1280 + ((h // 5) % 420)
    r = 680 + ((h // 11) % 220)
    d.arc([cx - r, cy - r, cx + r, cy + r], start=188, end=352,
          fill=accent + (255,), width=16)
    # second, shorter arc so the motif is visible on every colour
    r2 = r - 70
    d.arc([cx - r2, cy - r2, cx + r2, cy + r2], start=210, end=330,
          fill=_shift(color, 26) + (255,), width=8)
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))


def _icon_layer(kind, size, ink, plate):
    """Simple line icon, drawn large and scaled down so the stroke stays smooth."""
    S = 4
    layer = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ink = ink + (255,)
    plate = plate + (255,)

    def xy(px, py):
        return (px / 100 * size * S, py / 100 * size * S)

    sw = max(8, int(0.078 * size * S))

    def stroke(pts, width=None):
        width = sw if width is None else width
        d.line([xy(a, b) for a, b in pts], fill=ink, width=width, joint="curve")
        r = width / 2
        for a, b in (pts[0], pts[-1]):
            cx, cy = xy(a, b)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ink)

    def ellipse(a, b, c, e, **kw):
        d.ellipse([*xy(a, b), *xy(c, e)], **kw)

    def poly(pts, fill=None, outline=None):
        d.polygon([xy(a, b) for a, b in pts], fill=fill, outline=outline)

    def circ(a, b, c, e, fill=None, outline=None, width=None):
        ellipse(a, b, c, e, fill=fill, outline=outline or ink,
                width=sw if width is None else width)

    if kind == "music":
        ellipse(26, 58, 58, 90, fill=ink)
        stroke([(52, 70), (52, 18), (78, 30), (52, 46)], sw)
    elif kind == "globe":
        circ(16, 16, 84, 84, outline=ink)
        ellipse(38, 16, 62, 84, outline=ink, width=sw)
        stroke([(18, 50), (82, 50)], sw)
        stroke([(22, 34), (78, 34)], max(4, sw - 2))
        stroke([(22, 66), (78, 66)], max(4, sw - 2))
    elif kind == "book":
        stroke([(50, 18), (50, 84)], sw)
        poly([(18, 28), (48, 20), (48, 78), (18, 84)], outline=ink)
        stroke([(18, 28), (48, 20), (48, 78), (18, 84), (18, 28)], sw)
        stroke([(52, 20), (82, 28), (82, 84), (52, 78), (52, 20)], sw)
    elif kind == "drop":
        poly([(50, 12), (78, 52), (70, 74), (50, 88), (30, 74), (22, 52)], fill=ink)
    elif kind == "atom":
        ellipse(42, 42, 58, 58, fill=ink)
        ellipse(14, 36, 86, 64, outline=ink, width=sw)
        ellipse(36, 14, 64, 86, outline=ink, width=sw)
        ellipse(22, 22, 78, 78, outline=ink, width=sw)
    elif kind == "swords":
        stroke([(18, 82), (78, 18)], sw)
        stroke([(22, 18), (82, 82)], sw)
        stroke([(30, 30), (18, 42)], sw)
        stroke([(70, 30), (82, 42)], sw)
    elif kind == "flag":
        stroke([(28, 14), (28, 88)], sw)
        poly([(28, 16), (78, 16), (64, 36), (78, 56), (28, 56)], fill=ink)
    elif kind == "puzzle":
        for a, b in ((18, 18), (52, 18), (18, 52), (52, 52)):
            d.rounded_rectangle([*xy(a, b), *xy(a + 30, b + 30)],
                                radius=int(6 * S), outline=ink, width=sw)
    elif kind == "cricket":
        # handle on top, wide blade below
        poly([(58, 6), (68, 12), (56, 40), (76, 52), (64, 90), (42, 84), (38, 52), (50, 38)],
             fill=ink)
    elif kind == "lightning":
        poly([(58, 8), (28, 48), (46, 48), (34, 92), (76, 40), (54, 40)], fill=ink)
    elif kind == "sun":
        ellipse(34, 34, 66, 66, fill=ink)
        for a, b, c, e in (
            (50, 8, 50, 24), (50, 76, 50, 92), (8, 50, 24, 50), (76, 50, 92, 50),
            (18, 18, 30, 30), (70, 18, 82, 30), (18, 70, 30, 82), (70, 70, 82, 82),
        ):
            stroke([(a, b), (c, e)], sw)
    elif kind == "moon":
        ellipse(16, 14, 78, 84, fill=ink)
        ellipse(36, 10, 98, 80, fill=plate)
    elif kind == "clock":
        circ(14, 14, 86, 86, outline=ink)
        stroke([(50, 50), (50, 28)], sw)
        stroke([(50, 50), (68, 62)], sw)
    elif kind == "bank":
        poly([(50, 12), (88, 36), (12, 36)], fill=ink)
        stroke([(20, 40), (20, 78)], sw)
        stroke([(40, 40), (40, 78)], sw)
        stroke([(60, 40), (60, 78)], sw)
        stroke([(80, 40), (80, 78)], sw)
        stroke([(12, 82), (88, 82)], sw + 2)
    elif kind == "computer":
        d.rounded_rectangle([*xy(16, 14), *xy(84, 62)], radius=int(6 * S), outline=ink, width=sw)
        stroke([(50, 62), (50, 78)], sw)
        stroke([(30, 82), (70, 82)], sw)
    elif kind == "sound":
        poly([(18, 40), (36, 40), (54, 22), (54, 78), (36, 60), (18, 60)], fill=ink)
        d.arc([*xy(48, 30), *xy(78, 70)], 300, 60, fill=ink, width=sw)
        d.arc([*xy(48, 18), *xy(92, 82)], 300, 60, fill=ink, width=sw)
    elif kind == "planet":
        circ(22, 22, 78, 78, outline=ink)
        ellipse(8, 40, 92, 64, outline=ink, width=sw)
    elif kind == "rocket":
        poly([(50, 8), (70, 48), (70, 72), (50, 80), (30, 72), (30, 48)], fill=ink)
        poly([(30, 52), (14, 70), (30, 68)], fill=ink)
        poly([(70, 52), (86, 70), (70, 68)], fill=ink)
        ellipse(42, 40, 58, 56, fill=plate)
    elif kind == "spider":
        ellipse(36, 36, 64, 62, fill=ink)
        ellipse(42, 24, 58, 40, fill=ink)
        for pts in (
            [(40, 44), (14, 28)], [(44, 40), (22, 14)], [(56, 40), (78, 14)], [(60, 44), (86, 28)],
            [(40, 54), (12, 70)], [(44, 58), (24, 86)], [(56, 58), (76, 86)], [(60, 54), (88, 70)],
        ):
            stroke(pts, sw)
    elif kind == "bat":
        poly([(50, 46), (18, 28), (8, 48), (28, 52), (22, 70), (40, 58), (50, 78),
              (60, 58), (78, 70), (72, 52), (92, 48), (82, 28)], fill=ink)
    elif kind == "fish":
        ellipse(16, 32, 74, 72, fill=ink)
        poly([(70, 40), (94, 22), (90, 52), (94, 80), (70, 62)], fill=ink)
        poly([(40, 32), (58, 14), (62, 36)], fill=ink)
        ellipse(28, 44, 38, 54, fill=plate)
    elif kind == "cards":
        d.rounded_rectangle([*xy(28, 14), *xy(78, 78)], radius=int(6 * S), outline=ink, width=sw)
        d.rounded_rectangle([*xy(16, 26), *xy(62, 88)], radius=int(6 * S), fill=plate, outline=ink, width=sw)
    elif kind == "cube":
        poly([(50, 16), (84, 34), (50, 52), (16, 34)], outline=ink)
        stroke([(50, 16), (84, 34), (84, 68), (50, 86), (16, 68), (16, 34), (50, 16)], sw)
        stroke([(50, 52), (50, 86)], sw)
        stroke([(50, 52), (84, 34)], max(4, sw - 4))
    elif kind == "flask":
        stroke([(40, 14), (40, 36), (18, 80), (82, 80), (60, 36), (60, 14)], sw)
        stroke([(36, 14), (64, 14)], sw)
        stroke([(28, 62), (72, 62)], sw)
    elif kind == "river":
        stroke([(8, 32), (24, 22), (40, 32), (56, 22), (72, 32), (92, 22)], sw)
        stroke([(8, 52), (24, 42), (40, 52), (56, 42), (72, 52), (92, 42)], sw)
        stroke([(8, 72), (24, 62), (40, 72), (56, 62), (72, 72), (92, 62)], sw)
    elif kind == "bridge":
        d.arc([*xy(12, 28), *xy(88, 100)], 180, 360, fill=ink, width=sw)
        stroke([(10, 64), (90, 64)], sw)
        stroke([(28, 64), (28, 88)], sw)
        stroke([(72, 64), (72, 88)], sw)
    elif kind == "medal":
        poly([(32, 12), (50, 40), (28, 40)], fill=ink)
        poly([(68, 12), (72, 40), (50, 40)], fill=ink)
        circ(26, 36, 74, 88, outline=ink)
    elif kind == "fingerprint":
        for i, box in enumerate((
            (30, 20, 70, 88), (24, 28, 70, 88), (18, 38, 70, 88), (14, 50, 70, 88),
        )):
            d.arc([*xy(box[0], box[1]), *xy(box[2], box[3])],
                  80, 280, fill=ink, width=max(4, sw - 2))
    elif kind == "body":
        circ(36, 8, 64, 36, outline=ink)
        stroke([(50, 36), (50, 64)], sw)
        stroke([(22, 48), (78, 48)], sw)
        stroke([(50, 64), (28, 92)], sw)
        stroke([(50, 64), (72, 92)], sw)
    elif kind == "tennis":
        circ(14, 14, 86, 86, outline=ink)
        d.arc([*xy(-10, 20), *xy(70, 100)], 300, 60, fill=ink, width=sw)
        d.arc([*xy(30, 0), *xy(110, 80)], 120, 240, fill=ink, width=sw)
    elif kind == "mountain":
        poly([(8, 84), (38, 28), (52, 52), (70, 18), (96, 84)], outline=ink)
        stroke([(8, 84), (38, 28), (52, 52), (70, 18), (96, 84), (8, 84)], sw)
    elif kind == "ruins":
        for x, h in ((16, 70), (40, 84), (64, 58)):
            stroke([(x, 90), (x, 90 - h)], sw)
            stroke([(x - 8, 90 - h), (x + 10, 90 - h)], sw)
        stroke([(8, 90), (92, 90)], sw)
    else:  # quiz — question mark
        d.arc([*xy(28, 12), *xy(76, 58)], 200, 60, fill=ink, width=sw + 2)
        stroke([(52, 50), (52, 68)], sw)
        ellipse(44, 76, 60, 92, fill=ink)
    return layer.resize((size, size), Image.Resampling.LANCZOS)


def _paint_icon(img, q, kind, color):
    side = 156
    x0 = (C.W - side) // 2
    y0 = SAFE_TOP + 62
    plate = _shift(color, 30)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([x0, y0, x0 + side, y0 + side], radius=36,
                           fill=plate, outline=_shift(color, 68), width=3)
    pad = 30
    icon = _icon_layer(kind, side - 2 * pad, WHITE, plate)
    img.paste(icon, (x0 + pad, y0 + pad), icon)


def _paint_pill(draw):
    label = "QUIZ"
    font = latin_font(40)
    b = draw.textbbox((0, 0), label, font=font)
    tw, th = b[2] - b[0], b[3] - b[1]
    pad_x, pad_y = 36, 16
    w, h = tw + pad_x * 2, th + pad_y * 2
    x = (C.W - w) / 2
    y = 1488
    # Keep the chip inside the 4:5 centre crop.
    if y + h > SAFE_BOTTOM - 16:
        y = SAFE_BOTTOM - 16 - h
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=PILL_BG)
    draw.text((x + pad_x - b[0], y + pad_y - b[1]), label, font=font, fill=PILL_FG)


def make(q, out_path, n=1):
    """1080x1920 JPEG cover. `n` kept so build.py ka call same rehta hai."""
    spec = layout_cover(q)
    text = spec["text"]
    if leaks_answer(text, q):
        raise AssertionError(f"thumbnail me jawab leak: {text}")
    color = spec["bg"]
    img = Image.new("RGB", (C.W, C.H), color)
    _paint_arc(img, q, color)
    _paint_icon(img, q, spec["icon"], color)
    draw = ImageDraw.Draw(img)
    size = spec["font_size"]
    for ln, origin in zip(spec["lines"], spec["positions"]):
        _draw_line(draw, ln, origin, size, WHITE)
    _paint_pill(draw)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=88, optimize=True)
    if out_path.stat().st_size > 2_000_000:
        img.save(out_path, "JPEG", quality=75, optimize=True)
    return {
        "path": str(out_path),
        "text": text,
        "lines": spec["lines"],
        "font_size": spec["font_size"],
        "text_bounds": spec["text_bounds"],
        "qmark_bbox": spec["qmark_bbox"],
        "bg": color,
        "icon": spec["icon"],
    }


def set_thumbnail(yt, video_id, path):
    """thumbnails.set — fail ho to WARNING, exception upar nahi jaata."""
    from googleapiclient.http import MediaFileUpload
    try:
        yt.thumbnails().set(videoId=video_id,
                            media_body=MediaFileUpload(str(path), mimetype="image/jpeg")).execute()
        print(f"[thumb] set OK -> {video_id}")
        return True
    except Exception as e:
        print(f"[thumb] WARNING: thumbnails.set fail ({video_id}): {str(e)[:300]} "
              "— video upload theek hai, sirf custom thumbnail nahi laga. "
              "(Channel phone-verified ho aur token me youtube/youtube.upload scope ho.)")
        return False


def scheduled_private(rows, now=None):
    """Ledger rows jinka publish_at abhi future me hai (private + scheduled)."""
    now = now or datetime.now(timezone.utc)
    out = []
    for r in rows:
        pa = r.get("publish_at")
        if not pa or not r.get("video_id"):
            continue
        try:
            t = datetime.strptime(pa, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if t > now:
            out.append(r)
    return out


def backfill(apply=False, outdir=None):
    from pick import load_bank
    rows = json.loads((C.DATA / "uploads.json").read_text(encoding="utf-8"))
    todo = scheduled_private(rows)
    bank = {q["id"]: q for q in load_bank()}
    outdir = Path(outdir or C.OUT / "thumb_backfill")
    outdir.mkdir(parents=True, exist_ok=True)
    yt = None
    if apply and todo:
        from googleapiclient.discovery import build
        from upload import _creds
        yt = build("youtube", "v3", credentials=_creds(), cache_discovery=False)
    ok = []
    print(f"[backfill] {len(todo)} scheduled video(s), apply={apply}")
    for r in todo:
        vid = r["video_id"]
        qid = (r.get("question_ids") or [None])[0]
        q = bank.get(qid)
        if not q:
            print(f"[backfill] {vid}: question {qid} bank me nahi — skip")
            continue
        if yt is not None:
            # sirf private + scheduled par hi (status read-only check, 1 unit)
            it = yt.videos().list(part="status", id=vid).execute().get("items") or []
            st = it[0]["status"] if it else {}
            if st.get("privacyStatus") != "private" or not st.get("publishAt"):
                print(f"[backfill] {vid}: private+scheduled nahi ({st.get('privacyStatus')}) — skip")
                continue
        info = make(q, outdir / f"{vid}.jpg")
        print(f"[backfill] {vid} publish_at={r['publish_at']} text='{info['text']}'")
        if yt is not None and set_thumbnail(yt, vid, info["path"]):
            ok.append(vid)
    print(f"[backfill] thumbnails set: {', '.join(ok) or '(none)'}")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.backfill:
        backfill(apply=a.apply)
    else:
        ap.error("--backfill do")
