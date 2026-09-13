"""Salute karta fauji + lehrata tiranga — jawab se pehle wala CTA beat.

Sab code se banta hai (koi downloaded image nahi — copyright ka jhanjhat nahi).
Agar kabhi apni banayi tasveer lagani ho to assets/fauji.png (transparent,
khada fauji) daal do — wo drawn fauji ki jagah lagegi, jhanda phir bhi code se.

    python fauji.py        # preview: ../out/fauji_preview.png
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SAFFRON, WHITE, GREEN, NAVY = (255, 153, 51), (255, 255, 255), (19, 136, 8), (0, 0, 128)
OLIVE, OLIVE_D, OLIVE_L = (86, 104, 52), (58, 72, 34), (120, 138, 78)
SKIN, SKIN_D = (224, 170, 118), (190, 136, 90)
INK = (30, 24, 20)
ASSET = Path(__file__).resolve().parent.parent / "assets" / "fauji.png"
S2 = 2          # sab 2x par banao, phir chhota — kinare smooth


# ---------------------------------------------------------------- flag
def _flat_flag(w, h):
    img = Image.new("RGB", (w, h), WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, h // 3], fill=SAFFRON)
    d.rectangle([0, 2 * h // 3, w, h], fill=GREEN)
    cx, cy, r = w / 2, h / 2, h / 3 * 0.46
    lw = max(2, int(r * 0.07))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=NAVY, width=lw)
    for k in range(24):                                # Ashoka Chakra: 24 teeliyan
        a = 2 * math.pi * k / 24
        d.line([(cx, cy), (cx + r * math.cos(a), cy + r * math.sin(a))], fill=NAVY, width=max(1, lw // 2))
    hub = r * 0.18
    d.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=NAVY)
    return np.asarray(img).astype(np.float32)


_FLAG_CACHE = {}


def waving_flag(w, h, t, amp=None):
    """Flag attached on its RIGHT edge (pole), waving to the left. RGBA."""
    key = (w, h)
    if key not in _FLAG_CACHE:
        _FLAG_CACHE[key] = _flat_flag(w, h)
    flat = _FLAG_CACHE[key]
    amp = amp or h * 0.09
    out = np.zeros((h + int(2 * amp) + 2, w, 4), np.float32)
    for x in range(w):
        dist = (w - 1 - x) / w                          # 0 at pole, 1 at free end
        ph = 2 * math.pi * (dist * 1.25) - 2 * math.pi * 1.1 * t
        dy = amp * dist * math.sin(ph)
        shade = 1.0 + 0.22 * dist * math.cos(ph)        # fold ki roshni/chhaya
        y0 = int(round(amp + dy))
        out[y0:y0 + h, x, :3] = np.clip(flat[:, x, :] * shade, 0, 255)
        out[y0:y0 + h, x, 3] = 255
    return Image.fromarray(out.astype(np.uint8))


# ---------------------------------------------------------------- soldier
def _draw_soldier(w, h):
    """Flat cartoon fauji, aadha badan, salute karta hua. RGBA, size (w, h) at 2x."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = w * 0.5
    head_r = w * 0.2
    head_cy = h * 0.34
    # body (shoulders -> bottom)
    top = head_cy + head_r * 1.15
    d.rounded_rectangle([cx - w * 0.42, top, cx + w * 0.42, h + 40], int(w * 0.16), fill=OLIVE)
    for (px, py, pr, col) in [(0.25, 0.62, 0.07, OLIVE_D), (0.62, 0.7, 0.09, OLIVE_L), (0.4, 0.82, 0.08, OLIVE_D),
                              (0.75, 0.9, 0.07, OLIVE_D), (0.18, 0.93, 0.06, OLIVE_L), (0.55, 0.58, 0.05, OLIVE_L)]:
        d.ellipse([w * px - w * pr, h * py - w * pr * 0.7, w * px + w * pr, h * py + w * pr * 0.7], fill=col)
    # collar V + buttons + pocket lines
    d.polygon([(cx - w * 0.13, top), (cx, top + w * 0.2), (cx + w * 0.13, top)], fill=OLIVE_D)
    d.polygon([(cx - w * 0.08, top), (cx, top + w * 0.12), (cx + w * 0.08, top)], fill=SKIN_D)
    for k in range(3):
        by = top + w * 0.28 + k * w * 0.14
        d.ellipse([cx - 7, by - 7, cx + 7, by + 7], fill=OLIVE_D)
    d.rectangle([cx + w * 0.12, top + w * 0.3, cx + w * 0.32, top + w * 0.33], fill=OLIVE_D)
    # tiranga patch on the left shoulder (viewer's right)
    px, py = cx + w * 0.27, top + w * 0.1
    pw, ph = w * 0.12, w * 0.08
    d.rectangle([px, py, px + pw, py + ph / 3], fill=SAFFRON)
    d.rectangle([px, py + ph / 3, px + pw, py + 2 * ph / 3], fill=WHITE)
    d.rectangle([px, py + 2 * ph / 3, px + pw, py + ph], fill=GREEN)
    # neck
    d.rectangle([cx - head_r * 0.42, head_cy + head_r * 0.6, cx + head_r * 0.42, top + 10], fill=SKIN_D)
    # ears + head
    for sx in (-1, 1):
        ex = cx + sx * head_r * 0.98
        d.ellipse([ex - head_r * 0.2, head_cy - head_r * 0.1, ex + head_r * 0.2, head_cy + head_r * 0.3], fill=SKIN_D)
    d.ellipse([cx - head_r, head_cy - head_r * 1.05, cx + head_r, head_cy + head_r * 1.05], fill=SKIN)
    # helmet: dome + brim + net
    hb = head_cy - head_r * 0.28
    d.chord([cx - head_r * 1.12, hb - head_r * 1.05, cx + head_r * 1.12, hb + head_r * 1.0], 180, 360, fill=OLIVE)
    d.rounded_rectangle([cx - head_r * 1.22, hb - 6, cx + head_r * 1.22, hb + head_r * 0.2], 14, fill=OLIVE_D)
    for k in range(-3, 4):
        x0 = cx + k * head_r * 0.3
        d.line([(x0, hb - head_r * 0.9 + abs(k) * head_r * 0.13), (x0 + head_r * 0.2, hb)], fill=OLIVE_D, width=4)
    # eyebrows, eyes
    ey = head_cy + head_r * 0.02
    for sx in (-1, 1):
        ex = cx + sx * head_r * 0.38
        d.line([(ex - head_r * 0.2, ey - head_r * 0.24), (ex + head_r * 0.18, ey - head_r * 0.28)], fill=INK, width=9)
        d.ellipse([ex - head_r * 0.11, ey - head_r * 0.12, ex + head_r * 0.11, ey + head_r * 0.12], fill=INK)
        d.ellipse([ex - head_r * 0.03, ey - head_r * 0.08, ex + head_r * 0.03, ey - head_r * 0.02], fill=WHITE)
    # nose
    d.arc([cx - head_r * 0.12, ey + head_r * 0.05, cx + head_r * 0.12, ey + head_r * 0.32], 20, 160, fill=SKIN_D, width=6)
    # fauji wali moonchh
    my = ey + head_r * 0.42
    for sx in (-1, 1):
        d.polygon([(cx, my - head_r * 0.04), (cx + sx * head_r * 0.52, my - head_r * 0.02),
                   (cx + sx * head_r * 0.62, my - head_r * 0.2), (cx + sx * head_r * 0.5, my + head_r * 0.12),
                   (cx + sx * head_r * 0.08, my + head_r * 0.1)], fill=INK)
    # smile
    d.arc([cx - head_r * 0.3, my - head_r * 0.05, cx + head_r * 0.3, my + head_r * 0.35], 20, 160, fill=(150, 60, 50), width=8)
    # salute: right arm (viewer's left) up to the helmet brim
    # (haath brim par, aankh ke upar — pehle aankh dhak jaati thi; kohni canvas ke andar)
    sh = (cx - w * 0.3, top + w * 0.1)
    el = (cx - w * 0.4, top - w * 0.1)
    hand = (cx - head_r * 1.0, hb - head_r * 0.02)
    d.line([sh, el], fill=OLIVE, width=int(w * 0.12))
    d.line([el, hand], fill=OLIVE, width=int(w * 0.1))
    d.ellipse([el[0] - w * 0.06, el[1] - w * 0.06, el[0] + w * 0.06, el[1] + w * 0.06], fill=OLIVE)
    d.polygon([(hand[0] - head_r * 0.05, hand[1] + head_r * 0.08), (hand[0] + head_r * 0.62, hand[1] - head_r * 0.12),
               (hand[0] + head_r * 0.62, hand[1] + head_r * 0.04), (hand[0] + head_r * 0.02, hand[1] + head_r * 0.2)],
              fill=SKIN)
    return img


_SOLDIER = {}


def soldier(w, h):
    key = (w, h)
    if key not in _SOLDIER:
        if ASSET.exists():
            im = Image.open(ASSET).convert("RGBA")
            im.thumbnail((w, h), Image.LANCZOS)
            _SOLDIER[key] = im
        else:
            big = _draw_soldier(w * S2, h * S2)
            _SOLDIER[key] = big.resize((w, h), Image.LANCZOS)
    return _SOLDIER[key]


# ---------------------------------------------------------------- group
def group(w, h, t):
    """Fauji + pole + lehrata tiranga, RGBA (w x h). t = seconds (animation)."""
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    pole_x = int(w * 0.86)
    d.rounded_rectangle([pole_x - 7, int(h * 0.02), pole_x + 7, h], 6, fill=(120, 94, 64))
    d.ellipse([pole_x - 14, int(h * 0.02) - 14, pole_x + 14, int(h * 0.02) + 14], fill=(236, 186, 60))
    fw, fh = int(w * 0.72), int(w * 0.72 * 2 / 3)
    flag = waving_flag(fw, fh, t)
    out.alpha_composite(flag, (pole_x - fw, int(h * 0.03)))
    sw, sh = int(w * 0.8), int(h * 0.62)
    s = soldier(sw, sh)
    shadow = Image.new("RGBA", s.size, (0, 0, 0, 0))
    shadow.putalpha(s.getchannel("A").point(lambda a: a * 0.35))
    out.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)), (int(w * 0.02) + 6, h - s.height + 6))
    out.alpha_composite(s, (int(w * 0.02), h - s.height))
    return out


if __name__ == "__main__":
    prev = Image.new("RGBA", (3 * 330 + 40, 520), (46, 30, 90, 255))
    for i, t in enumerate((0.0, 0.3, 0.6)):
        prev.alpha_composite(group(330, 500, t), (10 + i * 340, 10))
    p = Path(__file__).resolve().parent.parent / "out"
    p.mkdir(exist_ok=True)
    prev.save(p / "fauji_preview.png")
    print(p / "fauji_preview.png")
