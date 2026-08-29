"""1080x1920 frames banata hai. Har frame ek PIL image.

Design rules (rajesh-ui-pro, Shorts variant):
- Mobile pe 3 inch me padhna hai -> question font >= 62px, option >= 52px.
- Safe zone: neeche 380px YouTube UI (title/CTA/like) dhak leta hai -> wahan kuch
  zaroori mat rakho. Timer ko bhi 1500px ke upar rakha hai.
- Contrast pehle, subtlety baad me. Bacchon ka content hai, bold chahiye.
"""
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config as C

LABELS = ["A", "B", "C", "D"]

# ---------------------------------------------------------------- emoji icons
# NotoColorEmoji CBDT bitmap font hai — Pillow use SIRF 109px pe khol sakta hai
# ("invalid pixel size" warna). Isliye 109 pe render karke neeche scale karte hain.
EMOJI_NATIVE = 109
_emoji_font = None
_emoji_cache = {}

ICONS = {}
_icons_path = C.DATA / "icons.json"
if _icons_path.exists():
    import json as _json
    ICONS = {k: v for k, v in
             _json.loads(_icons_path.read_text(encoding="utf-8")).items()
             if not k.startswith("_")}


def _emoji_ft():
    global _emoji_font
    if _emoji_font is None:
        import glob
        for f in glob.glob("/usr/share/fonts/**/*Emoji*.ttf", recursive=True):
            try:
                _emoji_font = ImageFont.truetype(f, EMOJI_NATIVE)
                break
            except Exception:
                continue
        if _emoji_font is None:
            _emoji_font = False        # dobara mat dhoondo
    return _emoji_font or None


def emoji_tile(ch, size):
    """Ek emoji ka RGBA tile. None agar emoji font hi na ho — us case me
    layout bina icon ke chal jaata hai, crash nahi hota."""
    key = (ch, size)
    if key in _emoji_cache:
        return _emoji_cache[key]
    ft = _emoji_ft()
    if ft is None:
        return None
    tile = Image.new("RGBA", (EMOJI_NATIVE + 40, EMOJI_NATIVE + 40), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((10, 10), ch, font=ft, embedded_color=True)
    bb = tile.getbbox()
    if not bb:
        _emoji_cache[key] = None
        return None
    tile = tile.crop(bb).resize((size, size), Image.LANCZOS)
    _emoji_cache[key] = tile
    return tile


def icons_for(q):
    """All-or-nothing: chaaron option ka icon ho tabhi dikhao. Aadha set
    bhadda lagta hai aur reading bhi slow karta hai."""
    if not ICONS:
        return None
    got = [ICONS.get(o) for o in q["opts"]]
    if not all(got):
        return None
    return got


# ---------------------------------------------------------------- fonts
def _has_devanagari(path) -> bool:
    """क (U+0915) aur ि (U+093F) dono chahiye — warna matra tut jaayegi."""
    try:
        f = ImageFont.truetype(str(path), 40)
        return bool(f.getmask("कि").getbbox())
    except Exception:
        return False


def _pick(cands, patterns):
    for p in cands:
        if Path(p).exists() and _has_devanagari(p):
            return str(p)
    # CI runner pe path alag ho sakta hai -> system scan
    import glob
    for pat in patterns:
        for p in sorted(glob.glob(f"/usr/share/fonts/**/{pat}", recursive=True)):
            if _has_devanagari(p):
                print(f"[render] font auto-detected: {p}")
                return p
    raise FileNotFoundError(
        "Devanagari font nahi mila.\n"
        "  Ubuntu/CI : sudo apt-get install -y fonts-noto-core fonts-indic\n"
        "  ya manually: assets/fonts/NotoSansDevanagari-Bold.ttf daal do"
    )


FONT_BOLD = _pick(C.FONT_CANDIDATES,
                  ["*Devanagari*Bold*.ttf", "Poppins-Bold.ttf",
                   "*Devanagari*.ttf", "Lohit-Devanagari.ttf"])
FONT_REG = _pick(C.FONT_CANDIDATES_REG,
                 ["*Devanagari*Regular*.ttf", "Poppins-Medium.ttf",
                  "*Devanagari*.ttf", "Lohit-Devanagari.ttf"])
_font_cache = {}


def F(size, bold=True):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)
    return _font_cache[key]


# ---------------------------------------------------------------- text utils
def text_w(draw, s, font):
    b = draw.textbbox((0, 0), s, font=font)
    return b[2] - b[0]


def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if text_w(draw, trial, font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_lines(draw, text, max_w, max_h, start=76, min_size=44, max_lines=4, bold=True):
    """Font size ghatate jao jab tak text box me fit na ho jaye."""
    size = start
    while size >= min_size:
        f = F(size, bold)
        lines = wrap(draw, text, f, max_w)
        lh = int(size * 1.34)
        if len(lines) <= max_lines and len(lines) * lh <= max_h:
            return f, lines, lh
        size -= 3
    f = F(min_size, bold)
    return f, wrap(draw, text, f, max_w), int(min_size * 1.34)


def centered(draw, lines, font, lh, cx, top, fill, stroke=0, stroke_fill=None):
    y = top
    for ln in lines:
        w = text_w(draw, ln, font)
        draw.text((cx - w // 2, y), ln, font=font, fill=fill,
                  stroke_width=stroke, stroke_fill=stroke_fill)
        y += lh
    return y


# ---------------------------------------------------------------- background
_bg_cache = {}


def background(seed=1):
    if seed in _bg_cache:
        return _bg_cache[seed]
    img = Image.new("RGB", (C.W, C.H))
    d = ImageDraw.Draw(img)
    top, bot = C.COLORS["bg_top"], C.COLORS["bg_bottom"]
    for y in range(C.H):
        t = y / C.H
        d.line([(0, y), (C.W, y)],
               fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    # confetti — bacchon wali vibe, halka rakha hai taki text na dabe
    rng = random.Random(seed)
    conf = ["#ffffff", "#ffe066", "#ff6b6b", "#4dabf7", "#69db7c"]
    ov = Image.new("RGBA", (C.W, C.H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for _ in range(90):
        x, y = rng.randint(0, C.W), rng.randint(0, C.H)
        r = rng.randint(6, 16)
        col = conf[rng.randrange(len(conf))]
        od.ellipse([x, y, x + r, y + r], fill=col + "55")
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    _bg_cache[seed] = img
    return img


def card(img, box, radius=44, fill=(255, 255, 255), shadow=True, outline=None, width=0):
    if shadow:
        sh = Image.new("RGBA", (C.W, C.H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle(
            [box[0] + 6, box[1] + 12, box[2] + 6, box[3] + 14], radius, fill=(0, 0, 0, 70))
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        img.alpha_composite(sh) if img.mode == "RGBA" else img.paste(
            Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB"), (0, 0))
    ImageDraw.Draw(img).rounded_rectangle(box, radius, fill=fill,
                                          outline=outline, width=width)
    return img


# ---------------------------------------------------------------- chrome
def banner(img, qnum=None, total=None, subject=None):
    """Top ribbon + left me 'सवाल 1/2' chip. Right side timer ke liye khaali
    chhoda hai — isliye chip center me nahi hai."""
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, -60, C.W, 210], 60, fill=C.COLORS["banner"])
    f = F(70)
    w = text_w(d, C.BRAND, f)
    d.text(((C.W - w) // 2, 62), C.BRAND, font=f, fill=C.COLORS["banner_text"],
           stroke_width=3, stroke_fill=(90, 8, 42))
    # 1 sawaal wali video me "सवाल 1/1" bekaar hai — sirf subject chip dikhao
    if qnum and total > 1:
        chip = f"सवाल {qnum}/{total}"
        cf = F(46)
        cw = text_w(d, chip, cf)
        d.rounded_rectangle([70, 240, 70 + cw + 68, 336], 48, fill=(255, 255, 255))
        d.text((104, 256), chip, font=cf, fill=C.COLORS["banner"])
    if subject:
        sf = F(44)
        sw = text_w(d, subject, sf)
        # Chip left me. Timer right me rehta hai, isliye takraav nahi hota.
        x0 = 70 if not (qnum and total > 1) else 70 + text_w(d, f"सवाल {qnum}/{total}", F(46)) + 92
        d.rounded_rectangle([x0, 244, x0 + sw + 60, 332], 44,
                            fill=C.COLORS["banner_text"])
        d.text((x0 + 30, 258), subject, font=sf, fill=C.COLORS["banner"])
    return img


FOOTER_Y = 1470          # iske neeche YouTube ka apna UI aata hai — khaali rakho


EMOJI_STRIP = "👇👆✅❌🎯🔔🤔💡🔥"


def footer(img, text=None, y=FOOTER_Y):
    """Screen text me emoji mat daalo — Poppins me emoji glyph nahi hai aur
    tofu box (□) render ho jaata hai. Option icons alag emoji font se aate hain."""
    d = ImageDraw.Draw(img)
    t = text or C.CTA_TEXT
    for ch in EMOJI_STRIP:
        t = t.replace(ch, "")
    t = " ".join(t.split())
    f = F(44)
    w = text_w(d, t, f)
    d.rounded_rectangle([(C.W - w) // 2 - 40, y, (C.W + w) // 2 + 40, y + 88],
                        44, fill=(255, 255, 255))
    d.text(((C.W - w) // 2, y + 18), t, font=f, fill=C.COLORS["banner"])
    hf = F(38, bold=False)
    hw = text_w(d, C.HANDLE, hf)
    d.text(((C.W - hw) // 2, y + 114), C.HANDLE, font=hf, fill=(255, 255, 255),
           stroke_width=2, stroke_fill=(150, 60, 20))
    return img


TIMER_CX, TIMER_CY, TIMER_R = 928, 288, 80


def timer_ring(img, remaining, total):
    """Top-right countdown ring. Yahan isliye rakha hai kyunki neeche options
    ki jagah hai — overlap ka risk zero. remaining = float seconds."""
    d = ImageDraw.Draw(img)
    cx, cy, r = TIMER_CX, TIMER_CY, TIMER_R
    box = [cx - r, cy - r, cx + r, cy + r]
    d.ellipse([cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8], fill=(255, 255, 255))
    d.arc(box, 0, 360, fill=C.COLORS["timer_ring_bg"], width=20)
    frac = max(0.0, min(1.0, remaining / total))
    if frac > 0:
        d.arc(box, -90, -90 + 360 * frac, fill=C.COLORS["timer_ring"], width=20)
    secs = max(0, math.ceil(remaining - 1e-6))
    f = F(86)
    s = str(secs)
    b = d.textbbox((0, 0), s, font=f)
    d.text((cx - (b[2] - b[0]) // 2 - b[0], cy - (b[3] - b[1]) // 2 - b[1]),
           s, font=f, fill=C.COLORS["timer_ring"])
    return img


# ---------------------------------------------------------------- panels
CARD_TOP = 382
CARD_X = 58
CARD_MIN_H, CARD_MAX_H = 250, 396
OPT_H = 112
OPT_GAP = 20
OPT_PAD = 42            # card ke neeche se options tak ka gap


def question_panel(q, qnum, total, highlight=None, dim_others=False):
    """highlight=None -> normal. highlight=idx -> us option ko green.
    Ye base image hai; timer per-frame iske upar paste hota hai.
    Return: (image, options_block_end_y) — reveal badge/footer isi se position hote hain."""
    img = background(qnum).convert("RGB")
    banner(img, qnum, total, q.get("sub"))

    d = ImageDraw.Draw(img)
    inner_w = C.W - 2 * CARD_X - 96
    f, lines, lh = fit_lines(d, q["q"], inner_w, CARD_MAX_H - 76,
                             start=78, min_size=48, max_lines=4)
    card_h = max(CARD_MIN_H, min(CARD_MAX_H, len(lines) * lh + 76))
    card_box = [CARD_X, CARD_TOP, C.W - CARD_X, CARD_TOP + card_h]
    card(img, card_box, fill=C.COLORS["card"])

    d = ImageDraw.Draw(img)
    top = CARD_TOP + (card_h - len(lines) * lh) // 2
    centered(d, lines, f, lh, C.W // 2, top, C.COLORS["q_text"])

    opt_top = card_box[3] + OPT_PAD
    icons = icons_for(q)
    text_x = 296 if icons else 206
    for i, opt in enumerate(q["opts"]):
        y = opt_top + i * (OPT_H + OPT_GAP)
        box = [70, y, C.W - 70, y + OPT_H]
        is_hit = (highlight is not None and i == highlight)
        if is_hit:
            bg, fg, lab = C.COLORS["correct_bg"], C.COLORS["correct"], C.COLORS["correct"]
            d.rounded_rectangle(box, 34, fill=bg, outline=C.COLORS["correct"], width=8)
        else:
            faded = dim_others and highlight is not None
            bg = (235, 235, 240) if faded else C.COLORS["opt_bg"]
            fg = (150, 150, 160) if faded else C.COLORS["opt_text"]
            lab = (170, 150, 155) if faded else C.COLORS["opt_label"]
            d.rounded_rectangle(box, 34, fill=bg, outline=(220, 222, 235), width=4)

        cx = 134
        d.ellipse([cx - 42, y + 14, cx + 42, y + OPT_H - 14],
                  fill=(255, 255, 255), outline=lab, width=6)
        lf = F(50)
        lb = d.textbbox((0, 0), LABELS[i], font=lf)
        d.text((cx - (lb[2] - lb[0]) // 2 - lb[0], y + OPT_H // 2 - (lb[3] + lb[1]) // 2),
               LABELS[i], font=lf, fill=lab)

        if icons:
            tile = emoji_tile(icons[i], 72)
            if tile is not None:
                if dim_others and not is_hit:
                    faded_tile = tile.copy()
                    faded_tile.putalpha(tile.getchannel("A").point(lambda a: a // 3))
                    tile = faded_tile
                img.paste(tile, (200, y + (OPT_H - 72) // 2), tile)

        of = F(56)
        max_w = C.W - text_x - 150
        while text_w(d, opt, of) > max_w and of.size > 34:
            of = F(of.size - 2)
        ob = d.textbbox((0, 0), opt, font=of)
        d.text((text_x, y + OPT_H // 2 - (ob[3] + ob[1]) // 2), opt, font=of, fill=fg)

        if is_hit:
            # Poppins me U+2713 glyph nahi hai (tofu box aata hai) -> haath se draw
            tx, ty = C.W - 150, y + OPT_H // 2
            d.line([(tx - 26, ty + 2), (tx - 8, ty + 22), (tx + 28, ty - 24)],
                   fill=C.COLORS["correct"], width=11, joint="curve")

    opt_end = opt_top + 4 * (OPT_H + OPT_GAP) - OPT_GAP
    return img, opt_end


def cta_panel(q, qnum, total):
    """Timer khatam, jawab abhi nahi. Options wahi rehte hain (viewer abhi bhi
    soch raha hai) aur upar se subscribe ka banner aata hai."""
    img, opt_end = question_panel(q, qnum, total)
    d = ImageDraw.Draw(img)
    t = "सब्सक्राइब करें"
    f = F(68)
    w = text_w(d, t, f)
    by = opt_end + 26
    d.rounded_rectangle([(C.W - w) // 2 - 52, by, (C.W + w) // 2 + 52, by + 104],
                        50, fill=C.COLORS["banner"], outline=C.COLORS["banner_text"],
                        width=6)
    d.text(((C.W - w) // 2, by + 16), t, font=f, fill=C.COLORS["banner_text"])
    footer(img, "जवाब आ रहा है…", y=max(FOOTER_Y, by + 140))
    return img


def reveal_panel(q, qnum, total):
    img, opt_end = question_panel(q, qnum, total, highlight=q["ans"], dim_others=True)
    d = ImageDraw.Draw(img)

    t = "सही जवाब!"
    f = F(64)
    w = text_w(d, t, f)
    by = opt_end + 22
    d.rounded_rectangle([(C.W - w) // 2 - 44, by, (C.W + w) // 2 + 44, by + 96],
                        46, fill=C.COLORS["correct"])
    d.text(((C.W - w) // 2, by + 12), t, font=f, fill=(255, 255, 255))
    y = by + 96

    why = (q.get("why") or "").strip()
    if why:
        # Reasoning card — yahi wo hissa hai jo "seekha kuch" feel deta hai.
        # Card ki height text ke hisaab se banti hai, fixed nahi.
        wf, wlines, wlh = fit_lines(d, why, C.W - 240, 230, start=44,
                                    min_size=32, max_lines=4, bold=False)
        h = len(wlines) * wlh + 56
        top = y + 20
        d.rounded_rectangle([80, top, C.W - 80, top + h], 30,
                            fill=(255, 255, 255), outline=C.COLORS["correct"], width=4)
        lf = F(34)
        d.text((116, top - 22), "क्यों?", font=lf, fill=C.COLORS["correct"],
               stroke_width=6, stroke_fill=(255, 255, 255))
        centered(d, wlines, wf, wlh, C.W // 2, top + 30, C.COLORS["opt_text"])
        y = top + h

    footer(img, "अगला सवाल आ रहा है…" if qnum < total else C.CTA_TEXT,
           y=max(FOOTER_Y, y + 28))
    return img


def title_panel(title, subtitle, seed=9, big=True):
    img = background(seed).convert("RGB")
    banner(img)
    card(img, [58, 520, C.W - 58, 1180], fill=C.COLORS["card"])
    d = ImageDraw.Draw(img)
    f, lines, lh = fit_lines(d, title, C.W - 240, 380, start=104 if big else 80,
                             min_size=56, max_lines=3)
    top = 620 + (380 - len(lines) * lh) // 2
    y = centered(d, lines, f, lh, C.W // 2, top, C.COLORS["q_text"])
    sf, slines, slh = fit_lines(d, subtitle, C.W - 260, 200, start=58, min_size=40,
                                max_lines=3, bold=False)
    centered(d, slines, sf, slh, C.W // 2, y + 40, (90, 96, 130))
    footer(img)
    return img
