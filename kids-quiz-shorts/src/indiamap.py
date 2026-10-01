"""India state map from a bundled, simplified GeoJSON.

assets/maps/india_states.geojson is Natural Earth 1:50m admin-1, public
domain, Douglas–Peucker simplified. See assets/maps/LICENSE.txt.

Reveal se pehle har rajya ek hi cream fill hai. Reveal par sirf sahi
rajya hara hota hai, aur wahi polygon outline bhi hai — fill alag shape
par nahi baithti.
"""
import json
import math
from functools import lru_cache

from PIL import ImageDraw

import config as C

_PATH = C.ASSETS / "maps" / "india_states.geojson"

ALIASES = {
    "बंगाल": "पश्चिम बंगाल",
    "पश्चिमबंगाल": "पश्चिम बंगाल",
    "जम्मू कश्मीर": "जम्मू और कश्मीर",
    "जम्मू-कश्मीर": "जम्मू और कश्मीर",
    "हिमाचल": "हिमाचल प्रदेश",
    "उड़ीसा": "ओडिशा",
    "ओडिशा": "ओडिशा",
    "आंध्र": "आंध्र प्रदेश",
    "तमिल नाडु": "तमिलनाडु",
    "उत्तराखण्ड": "उत्तराखंड",
}

_GEO_HINTS = ("राज्य", "नदी", "मंदिर", "नृत्य", "त्योहार", "रण", "पोर्ट", "बंदरगाह",
              "उद्यान", "राजधानी", "शहर", "पर्वत")

# Equirectangular squeeze so a degree of longitude isn't stretched.
_COS = math.cos(math.radians(23.0))

PLAIN_FILL = (253, 246, 230)
ANSWER_FILL = (22, 163, 74)
OCEAN = (186, 214, 236)
OUTLINE = (90, 78, 62)

# Last draw(); tests use this to check the green fill against the outline.
LAST_LAYOUT = None


@lru_cache(maxsize=1)
def _fc():
    return json.loads(_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _by_name():
    return {f["properties"]["name"]: f["geometry"] for f in _fc()["features"]}


def _polys(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    return geom["coordinates"]


def _rings_of(name):
    geom = _by_name().get(name)
    if not geom:
        return []
    return _polys(geom)


@lru_cache(maxsize=1)
def _bounds():
    xs, ys = [], []

    def walk(c):
        if c and isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
            return
        for part in c:
            walk(part)

    for geom in _by_name().values():
        walk(geom["coordinates"])
    return min(xs), min(ys), max(xs), max(ys)


def _view_size():
    minx, miny, maxx, maxy = _bounds()
    return (maxx - minx) * _COS, (maxy - miny)


def resolve(name: str):
    if not name:
        return None
    key = " ".join(name.replace("-", " ").split())
    if key in _by_name():
        return key
    return ALIASES.get(key)


def for_question(q: dict):
    """Option-aligned canonical state names, ya None agar naksha bekaar ho."""
    names = [resolve(o.strip()) for o in q.get("opts") or []]
    known = [n for n in names if n]
    if len(known) < 2 or len(names) != 4:
        return None
    blob = f"{q.get('q', '')} {q.get('sub', '')} {q.get('why', '')}"
    geographic = q.get("sub") == "भारत" or any(h in blob for h in _GEO_HINTS)
    if not geographic and len(known) < 3:
        return None
    return names


def _layout(box):
    minx, miny, maxx, maxy = _bounds()
    vw, vh = _view_size()
    x0, y0, x1, y1 = box
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    pad = 8
    scale = min((w - 2 * pad) / vw, (h - 2 * pad) / vh)
    ox = x0 + (w - vw * scale) / 2
    oy = y0 + (h - vh * scale) / 2
    return {
        "box": box, "ox": ox, "oy": oy, "scale": scale,
        "minx": minx, "maxy": maxy,
    }


def _screen(lon, lat, lay):
    x = lay["ox"] + (lon - lay["minx"]) * _COS * lay["scale"]
    y = lay["oy"] + (lay["maxy"] - lat) * lay["scale"]
    return (x, y)


def _screen_ring(ring, lay):
    return [_screen(lon, lat, lay) for lon, lat in ring]


def _inside(x, y, pts) -> bool:
    n = len(pts)
    hit = False
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            denom = (y2 - y1) or 1e-12
            xcross = (x2 - x1) * (y - y1) / denom + x1
            if x < xcross:
                hit = not hit
    return hit


def _ring_area(pts) -> float:
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def covers(name: str, x: int, y: int, layout=None) -> bool:
    """Screen pixel is inside this state's outline (same polygon as the fill)."""
    lay = layout or LAST_LAYOUT
    if not lay:
        return False
    for poly in _rings_of(name):
        if not poly:
            continue
        outer = _screen_ring(poly[0], lay)
        if not _inside(x, y, outer):
            continue
        for hole in poly[1:]:
            if _inside(x, y, _screen_ring(hole, lay)):
                break
        else:
            return True
    return False


def _interior_view_point(ring):
    """A lon/lat that sits inside the ring. Centroid, warna grid scan."""
    pts = ring[:-1] if ring[0] == ring[-1] else ring
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    if _inside(cx, cy, pts):
        return cx, cy
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    step = max((max(xs) - min(xs)) / 24, 0.05)
    y = min(ys)
    while y <= max(ys):
        x = min(xs)
        while x <= max(xs):
            if _inside(x, y, pts):
                return x, y
            x += step
        y += step
    return pts[0]


def locate(box, name):
    """State ke andar ek screen pixel (tests)."""
    lay = _layout(box)
    best, best_a = None, -1.0
    for poly in _rings_of(name):
        if not poly:
            continue
        area = _ring_area(poly[0])
        if area > best_a:
            best, best_a = poly[0], area
    if best is None:
        raise KeyError(name)
    lon, lat = _interior_view_point(best)
    x, y = _screen(lon, lat, lay)
    return int(round(x)), int(round(y))


def ink_width(box) -> float:
    """Kitne pixel chaudi par desh ka silhouette aata hai."""
    lay = _layout(box)
    vw, _vh = _view_size()
    return vw * lay["scale"]


def draw(img, box, option_states, correct=None):
    """box = (x0, y0, x1, y1).

    correct None: saare rajya ek cream. correct set: sirf wahi polygon hara,
    outline usi ring par.
    """
    global LAST_LAYOUT
    lay = _layout(box)
    LAST_LAYOUT = lay
    # option_states jaan-boojh kar alag rang nahi lete.
    _ = option_states
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y0, x1, y1], 28, fill=OCEAN)

    def paint(name, fill):
        for poly in _rings_of(name):
            if not poly:
                continue
            d.polygon(_screen_ring(poly[0], lay), fill=fill, outline=OUTLINE)
            for hole in poly[1:]:
                d.polygon(_screen_ring(hole, lay), fill=OCEAN, outline=OUTLINE)

    names = list(_by_name())
    names.sort(key=lambda n: sum(_ring_area(p[0]) for p in _rings_of(n) if p))
    if correct in names:
        names.remove(correct)
    for name in names:
        paint(name, PLAIN_FILL)
    if correct in _by_name():
        paint(correct, ANSWER_FILL)
        for poly in _rings_of(correct):
            for ring in poly:
                pts = _screen_ring(ring, lay)
                if len(pts) >= 2:
                    d.line(pts + pts[:1], fill=(12, 70, 36), width=3)
    return img
