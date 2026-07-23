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

# Excalidraw-ish palette on a near-black canvas
INK = (236, 236, 236)
HIGHLIGHT = (245, 197, 66)      # amber marker
POP = (255, 107, 94)            # coral, for the "against you" beats
COOL = (94, 200, 255)           # sky, for neutral/technical
GREEN = (86, 211, 140)
PAPER = (16, 19, 25)


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
    """Hand-drawn chart via matplotlib's xkcd mode — the Excalidraw look, but
    plotting the script's real numbers. Returns False if the data is unusable."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = chart.get("labels") or []
    values = chart.get("values") or []
    if not labels or not values or len(labels) != len(values):
        return False
    try:
        values = [float(v) for v in values]
    except (TypeError, ValueError):
        return False

    ink = "#ECECEC"
    accent = "#F5C542"
    w, h = size
    with plt.xkcd(scale=1.1, length=110, randomness=2):
        fig, ax = plt.subplots(figsize=(w / 100, h / 100), dpi=100)
        fig.patch.set_facecolor("#101319")
        # xkcd mode draws a sketchy dashed frame around the figure — kill it
        fig.patch.set_linewidth(0)
        fig.patch.set_edgecolor("#101319")
        ax.set_facecolor("#101319")
        ax.patch.set_edgecolor("none")

        kind = str(chart.get("type", "bar")).lower()
        if kind == "line":
            ax.plot(range(len(values)), values, color=accent, linewidth=4, marker="o",
                    markersize=12, markerfacecolor=accent, markeredgecolor=accent)
        else:
            ax.bar(range(len(values)), values, color=accent, width=0.55)

        for i, v in enumerate(values):
            ax.annotate(f"{v:g}", (i, v), textcoords="offset points", xytext=(0, 14),
                        ha="center", color=ink, fontsize=22)

        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, color=ink, fontsize=22)
        ax.tick_params(colors=ink, labelsize=20)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
            ax.spines[spine].set_color("none")
        for spine in ("bottom", "left"):
            ax.spines[spine].set_color(ink)
            ax.spines[spine].set_linewidth(2.5)
        ax.set_ylim(0, max(values) * 1.28)
        # clear of the title band above and the caption zone below
        fig.subplots_adjust(left=0.10, right=0.95, top=0.72, bottom=0.34)
        fig.savefig(path, facecolor="#101319")
        plt.close(fig)
    return True
