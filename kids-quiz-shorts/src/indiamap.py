"""Schematic India map. State polygons live in assets/maps/india_schematic.json.

Sirf tab dikhana hai jab options mein se kam se kam do asli rajya hon —
warna naksha sawaal ko madad nahi karta. Reveal se pehle saara desh ek
jaisa outline hai (koi rajya alag rang nahi — warna sahi state pehle khul
jaati hai). Reveal par sirf sahi rajya hara hota hai.
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


PLAIN_FILL = (253, 246, 230)
ANSWER_FILL = (22, 163, 74)


def _layout(box):
    view, states = _spec()
    x0, y0, x1, y1 = box
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    pad = 8
    vw, vh = view
    scale = min((w - 2 * pad) / vw, (h - 2 * pad) / vh)
    ox = x0 + (w - vw * scale) / 2
    oy = y0 + (h - vh * scale) / 2
    return states, ox, oy, scale


def _inside(x, y, pts) -> bool:
    n = len(pts)
    hit = False
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xcross = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xcross:
                hit = not hit
    return hit


def locate(box, name):
    """State ke andar ek pixel (tests). Centroid bahar ho to bbox scan."""
    states, ox, oy, scale = _layout(box)
    pts = states[name]
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    if not _inside(cx, cy, pts):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        found = None
        step = 0.8
        y = min(ys)
        while y <= max(ys) and found is None:
            x = min(xs)
            while x <= max(xs):
                if _inside(x, y, pts):
                    found = (x, y)
                    break
                x += step
            y += step
        if found is None:
            found = pts[0]
        cx, cy = found
    return int(round(ox + cx * scale)), int(round(oy + cy * scale))


def draw(img, box, option_states, correct=None):
    """box = (x0, y0, x1, y1). option_states = is sawaal ke rajya.

    correct None: har state ek hi cream fill — option states ko gold mat do,
    warna Gujarat jaisa peninsula jawab jaisa dikhta hai. correct set: sirf
    wahi state hara.
    """
    states, ox, oy, scale = _layout(box)
    x0, y0, x1, y1 = box

    def poly(pts):
        return [(ox + px * scale, oy + py * scale) for px, py in pts]

    # option_states jaan-boojh kar alag rang nahi lete — warna sahi state
    # timer frame par pehle hi highlight ho jaati hai.
    _ = option_states
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y0, x1, y1], 18, fill=(232, 242, 250))
    for name, pts in states.items():
        if correct and name == correct:
            fill, outline = ANSWER_FILL, (12, 90, 40)
        else:
            fill, outline = PLAIN_FILL, (180, 164, 140)
        d.polygon(poly(pts), fill=fill, outline=outline)
    if correct and correct in states:
        ring = poly(states[correct])
        d.line(ring + ring[:1], fill=(40, 40, 40), width=2)
    return img
