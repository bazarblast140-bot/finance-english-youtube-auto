"""Schematic India map. State polygons live in assets/maps/india_schematic.json.

Sirf tab dikhana hai jab options mein se kam se kam do asli rajya hon —
warna naksha sawaal ko madad nahi karta. Sahi rajya tab rangta hai jab
reveal highlight de (question ke dauran saare ummeedwaar ek jaise dikhte hain,
taaki jawab pehle na khule).
"""
import json
from functools import lru_cache

from PIL import Image, ImageDraw

import config as C

_PATH = C.ASSETS / "maps" / "india_schematic.json"

ALIASES = {
    "बंगाल": "पश्चिम बंगाल",
    "पश्चिमबंगाल": "पश्चिम बंगाल",
    "जम्मू कश्मीर": "जम्मू और कश्मीर",
    "जम्मू-कश्मीर": "जम्मू और कश्मीर",
    "हिमाचल": "हिमाचल प्रदेश",
    "उड़ीसा": "ओडिशा",
    "आंध्र": "आंध्र प्रदेश",
}

_GEO_HINTS = ("राज्य", "नदी", "मंदिर", "नृत्य", "त्योहार", "रण", "पोर्ट", "बंदरगाह",
              "उद्यान", "राजधानी", "शहर", "पर्वत")


@lru_cache(maxsize=1)
def _spec():
    data = json.loads(_PATH.read_text(encoding="utf-8"))
    return data["view"], data["states"]


def resolve(name: str):
    if not name:
        return None
    key = " ".join(name.replace("-", " ").split())
    _, states = _spec()
    if key in states:
        return key
    return ALIASES.get(key)


def for_question(q: dict):
    """Option-aligned canonical state names, ya None agar naksha bekaar ho.

    List mein None un options ke liye rehta hai jo rajya nahi hain.
    """
    names = [resolve(o.strip()) for o in q.get("opts") or []]
    known = [n for n in names if n]
    if len(known) < 2 or len(names) != 4:
        return None
    blob = f"{q.get('q', '')} {q.get('sub', '')} {q.get('why', '')}"
    geographic = q.get("sub") == "भारत" or any(h in blob for h in _GEO_HINTS)
    if not geographic and len(known) < 3:
        return None
    return names


def draw(img, box, option_states, correct=None):
    """box = (x0, y0, x1, y1). option_states = is sawaal ke rajya.

    correct diya ho to wahi hara. Na ho to saare ummeedwaar ek rang (gold),
    baaki desh halka — jawab spoil nahi hota.
    """
    view, states = _spec()
    x0, y0, x1, y1 = box
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    pad = 8
    vw, vh = view
    sx = (w - 2 * pad) / vw
    sy = (h - 2 * pad) / vh
    scale = min(sx, sy)
    ox = x0 + (w - vw * scale) / 2
    oy = y0 + (h - vh * scale) / 2

    def poly(pts):
        return [(ox + px * scale, oy + py * scale) for px, py in pts]

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y0, x1, y1], 18, fill=(232, 242, 250))
    wanted = {s for s in option_states if s}
    for name, pts in states.items():
        if name == correct:
            fill, outline = (22, 163, 74), (12, 90, 40)
            width = 4
        elif name in wanted and correct is None:
            fill, outline = (245, 197, 66), (146, 96, 16)
            width = 3
        elif name in wanted and correct is not None:
            fill, outline = (226, 232, 240), (140, 150, 165)
            width = 2
        else:
            fill, outline = (253, 246, 230), (180, 164, 140)
            width = 2
        d.polygon(poly(pts), fill=fill, outline=outline)
    # outline dobara, taaki padosi border na ghul jaaye
    for name, pts in states.items():
        if name == correct or (correct is None and name in wanted):
            d.line(poly(pts) + poly(pts)[:1], fill=(40, 40, 40), width=2)
    return img
