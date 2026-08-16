"""Hand-drawn (Excalidraw-style) drawing helpers.

Everything here is deterministic: the seed comes from the shot index, so a given
shot renders identically on every run. Wobble that changes between renders would
read as flicker, not as hand-drawn.

Two layers of "hand-drawn":
  - PIL primitives below: marker highlights, rough underlines and boxes, arrows.
  - matplotlib's xkcd() mode in chart_png(): sketchy axes and lines for real data.
"""
import math, random

from PIL import Image, ImageDraw, ImageFilter

# Wealth-Logic-style light board (white canvas, dark ink)
INK = (28, 28, 32)
HIGHLIGHT = (245, 197, 66)      # amber marker
POP = (220, 60, 50)             # red for "against you" / down arrows
COOL = (40, 120, 200)           # calm blue
GREEN = (34, 160, 90)
PAPER = (250, 250, 252)         # near-white background


def _rng(seed):
    return random.Random(seed)


def _wobble(p1, p2, rng, jitter, steps=10):
    """Points along p1->p2 with perpendicular noise — one hand-drawn stroke."""
    (x1, y1), (x2, y2) = p1, p2
    dx, dy = x2 - x1, y2 - y1
    length = max(1.0, math.hypot(dx, dy))
    nx, ny = -dy / length, dx / length
    pts = []
    for i in range(steps + 1):
        t = i / steps
        # taper the jitter at the ends so strokes meet cleanly
        damp = math.sin(math.pi * t) ** 0.5
        off = rng.uniform(-jitter, jitter) * damp
        pts.append((x1 + dx * t + nx * off, y1 + dy * t + ny * off))
    return pts


def rough_line(d, p1, p2, color, width=6, seed=0, passes=2, jitter=3.0):
    """A line drawn the way a human would: two overlapping imperfect strokes."""
    rng = _rng(seed)
    for _ in range(passes):
        d.line(_wobble(p1, p2, rng, jitter), fill=color, width=width, joint="curve")


def rough_rect(d, box, color, width=5, seed=0, jitter=3.0):
    x0, y0, x1, y1 = box
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for i in range(4):
        rough_line(d, corners[i], corners[(i + 1) % 4], color, width, seed + i, 2, jitter)


def marker_highlight(size, box, color, seed=0, alpha=238):
    """A marker swipe as its own RGBA layer, composited UNDER the text.

    Near-opaque on purpose: a translucent amber over a near-black canvas goes
    muddy olive. A solid swipe with dark text on top is what actually reads —
    and it is the strongest attention cue on the frame, so it has to be clean.
    Draw the highlighted words in PAPER, not INK, over this.
    """
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rng = _rng(seed)
    x0, y0, x1, y1 = box
    x0 -= rng.randint(12, 24)
    x1 += rng.randint(12, 24)

    # one filled shape with hand-drawn top and bottom edges — no nib banding
    steps = 16
    top = [(x0 + (x1 - x0) * i / steps, y0 + rng.uniform(-5, 5)) for i in range(steps + 1)]
    bottom = [(x0 + (x1 - x0) * i / steps, y1 + rng.uniform(-5, 5)) for i in range(steps, -1, -1)]
    d.polygon(top + bottom, fill=color + (alpha,))
    return layer.filter(ImageFilter.GaussianBlur(2.0))


def rough_underline(d, x0, x1, y, color, width=7, seed=0):
    rough_line(d, (x0, y), (x1, y + _rng(seed).randint(-3, 3)), color, width, seed, 2, 3.5)


def rough_arrow(d, p1, p2, color, width=6, seed=0, head=26):
    rough_line(d, p1, p2, color, width, seed, 2, 2.5)
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    for sign in (+1, -1):
        a = ang + sign * math.radians(150)
        tip = (p2[0] + head * math.cos(a), p2[1] + head * math.sin(a))
        rough_line(d, p2, tip, color, width, seed + 7, 1, 1.5)


def chart_png(chart, path, size=(1920, 1080)):
    """Hand-drawn chart via matplotlib xkcd — light board, multi-bar preferred."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = list(chart.get("labels") or [])
    values = list(chart.get("values") or [])
    if not labels or not values or len(labels) != len(values):
        return False
    try:
        values = [float(v) for v in values]
    except (TypeError, ValueError):
        return False

    # Single-bar charts look empty — expand to a simple before/after style pair
    if len(values) == 1:
        labels = [str(labels[0])[:18], "context"]
        values = [values[0], max(values[0] * 0.35, 1.0)]

    ink = "#1C1C20"
    accent = "#F5C542"
    accent2 = "#DC3C32"
    paper = "#FAFAFC"
    w, h = size
    colors = [accent if i % 2 == 0 else accent2 for i in range(len(values))]
    if len(values) >= 3:
        colors = [accent, "#2880C8", accent2][:len(values)]
        while len(colors) < len(values):
            colors.append(accent)

    with plt.xkcd(scale=1.0, length=100, randomness=2):
        fig, ax = plt.subplots(figsize=(w / 100, h / 100), dpi=100)
        fig.patch.set_facecolor(paper)
        fig.patch.set_linewidth(0)
        ax.set_facecolor(paper)

        kind = str(chart.get("type", "bar")).lower()
        if kind == "line":
            ax.plot(range(len(values)), values, color=accent, linewidth=4, marker="o",
                    markersize=12, markerfacecolor=accent, markeredgecolor=ink)
        else:
            ax.bar(range(len(values)), values, color=colors[:len(values)], width=0.55,
                   edgecolor=ink, linewidth=1.5)

        for i, v in enumerate(values):
            ax.annotate(f"{v:g}", (i, v), textcoords="offset points", xytext=(0, 12),
                        ha="center", color=ink, fontsize=22, fontweight="bold")

        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels([str(x)[:16] for x in labels], color=ink, fontsize=20)
        ax.tick_params(colors=ink, labelsize=18)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for spine in ("bottom", "left"):
            ax.spines[spine].set_color(ink)
            ax.spines[spine].set_linewidth(2.0)
        ax.set_ylim(0, max(values) * 1.32 if max(values) > 0 else 1)
        fig.subplots_adjust(left=0.10, right=0.95, top=0.70, bottom=0.32)
        fig.savefig(path, facecolor=paper)
        plt.close(fig)
    return True


def draw_host(size=520):
    """Simple consistent lab-coat host (Wealth-Logic energy), RGBA."""
    from PIL import Image, ImageDraw
    s = size
    img = Image.new("RGBA", (s, int(s * 1.35)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # scale helpers
    def xy(a, b):
        return (int(a * s), int(b * s))

    # head
    d.ellipse([xy(0.28, 0.02), xy(0.72, 0.38)], fill=(255, 214, 186, 255), outline=(30, 30, 34, 255), width=4)
    # hair
    d.ellipse([xy(0.28, 0.02), xy(0.72, 0.22)], fill=(30, 30, 34, 255))
    d.rectangle([xy(0.28, 0.14), xy(0.72, 0.22)], fill=(255, 214, 186, 255))
    # eyes
    d.ellipse([xy(0.40, 0.16), xy(0.46, 0.21)], fill=(30, 30, 34, 255))
    d.ellipse([xy(0.54, 0.16), xy(0.60, 0.21)], fill=(30, 30, 34, 255))
    # smile
    d.arc([xy(0.40, 0.20), xy(0.60, 0.32)], 20, 160, fill=(30, 30, 34, 255), width=3)
    # neck
    d.rectangle([xy(0.44, 0.36), xy(0.56, 0.44)], fill=(255, 214, 186, 255))
    # lab coat body
    d.polygon([
        xy(0.18, 0.44), xy(0.82, 0.44), xy(0.90, 1.20), xy(0.10, 1.20)
    ], fill=(250, 250, 252, 255), outline=(30, 30, 34, 255))
    # coat outline
    d.line([xy(0.18, 0.44), xy(0.10, 1.20)], fill=(30, 30, 34, 255), width=4)
    d.line([xy(0.82, 0.44), xy(0.90, 1.20)], fill=(30, 30, 34, 255), width=4)
    # tie
    d.polygon([xy(0.48, 0.44), xy(0.52, 0.44), xy(0.54, 0.70), xy(0.50, 0.74), xy(0.46, 0.70)],
              fill=(30, 30, 34, 255))
    # coat buttons
    for by in (0.58, 0.70, 0.82):
        d.ellipse([xy(0.48, by), xy(0.52, by + 0.04)], fill=(30, 30, 34, 255))
    # pointing arm (right)
    d.line([xy(0.78, 0.55), xy(1.05, 0.48)], fill=(255, 214, 186, 255), width=18)
    d.ellipse([xy(1.00, 0.44), xy(1.10, 0.54)], fill=(255, 214, 186, 255), outline=(30, 30, 34, 255), width=3)
    # left arm
    d.line([xy(0.22, 0.55), xy(0.08, 0.75)], fill=(255, 214, 186, 255), width=16)
    return img


def draw_icon(name, size=200):
    """Minimal flat icons when asset PNG missing."""
    from PIL import Image, ImageDraw
    name = (name or "").lower().strip()
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ink = (28, 28, 32, 255)
    accent = (245, 197, 66, 255)
    red = (220, 60, 50, 255)
    m = size * 0.1
    if name in ("car", "vehicle"):
        d.rounded_rectangle([m, size*0.4, size-m, size*0.7], radius=12, fill=red, outline=ink, width=3)
        d.ellipse([size*0.2, size*0.62, size*0.38, size*0.8], fill=ink)
        d.ellipse([size*0.62, size*0.62, size*0.8, size*0.8], fill=ink)
    elif name in ("cash", "money", "savings"):
        d.rounded_rectangle([m, m*2, size-m, size-m*2], radius=10, fill=(86, 211, 140, 255), outline=ink, width=3)
        d.ellipse([size*0.35, size*0.35, size*0.65, size*0.65], outline=ink, width=4)
    elif name in ("calendar", "month", "time"):
        d.rounded_rectangle([m, m*2, size-m, size-m], radius=10, fill=(250, 250, 252, 255), outline=ink, width=3)
        d.rectangle([m, m*2, size-m, size*0.35], fill=red)
        d.text((size*0.35, size*0.5), "31", fill=ink)
    elif name in ("loan", "paper", "debt"):
        d.rounded_rectangle([m*1.5, m, size-m*1.5, size-m], radius=6, fill=(250, 250, 252, 255), outline=ink, width=3)
        for i in range(4):
            y = size*0.35 + i * size*0.12
            d.line([size*0.28, y, size*0.72, y], fill=ink, width=3)
    elif name in ("loop", "cycle", "again"):
        d.arc([m, m, size-m, size-m], 30, 300, fill=ink, width=10)
        d.polygon([size*0.75, size*0.2, size*0.95, size*0.35, size*0.7, size*0.4], fill=ink)
    elif name in ("arrow_down", "down", "loss"):
        d.polygon([size*0.45, m, size*0.55, m, size*0.55, size*0.55,
                   size*0.75, size*0.55, size*0.5, size*0.9, size*0.25, size*0.55,
                   size*0.45, size*0.55], fill=red, outline=ink)
    elif name in ("arrow_up", "up", "gain"):
        d.polygon([size*0.5, m, size*0.75, size*0.45, size*0.55, size*0.45,
                   size*0.55, size*0.9, size*0.45, size*0.9, size*0.45, size*0.45,
                   size*0.25, size*0.45], fill=(34, 160, 90, 255), outline=ink)
    else:
        # default: amber circle badge
        d.ellipse([m, m, size-m, size-m], fill=accent, outline=ink, width=4)
    return img

