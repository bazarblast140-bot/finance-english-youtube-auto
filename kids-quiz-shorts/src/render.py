"""1080x1920 frames banata hai. Har frame ek PIL image.

Design rules (rajesh-ui-pro, Shorts variant):
- Mobile pe 3 inch me padhna hai -> question font >= 62px, option >= 52px.
- Safe zone: neeche ~250px YouTube UI (title/CTA) aur right rail (like/comment)
  x>890. Uske upar ka hissa khali mat chhodo — visual + options wahan tak jaate hain.
- Right rail: like / dislike / comment / share buttons right kinare par ~900px
  ke baad baithte hain. Options, map, aur neeche wala sab RAIL_X se pehle khatam.
- Contrast pehle, subtlety baad me. Audience general GK hai — bold, padhne layak.
"""
import math
import random
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageFilter

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


def _glyph_real(path, ch: str) -> bool:
    """Missing glyph (.notdef tofu) ko 'hai' mat maano.

    Noto Sans Devanagari Bold mein Latin nahi hota — A-D aur QUIZ PATHSHALA
    khali box ban jaate hain, getbbox phir bhi sach bolta hai. Isliye .notdef
    se byte-compare karte hain.
    """
    try:
        font = ImageFont.truetype(str(path), 80)
        missing = font.getmask("\uffff")
        got = font.getmask(ch)
        if not got.getbbox():
            return False
        # ImagingCore par tobytes hamesha nahi hota. Histogram .notdef se alag
        # ho to glyph asli hai (tofu box nahi).
        return got.histogram() != missing.histogram()
    except Exception:
        return False


def _font_ok(path) -> bool:
    if not _has_devanagari(path):
        return False
    for ch in "ABCDQUIZPATHSHALA":
        if not _glyph_real(path, ch):
            return False
    return True


def _pick(cands, patterns):
    for p in cands:
        if Path(p).exists() and _font_ok(p):
            return str(p)
    # CI runner pe path alag ho sakta hai -> system scan.
    # Sirf Devanagari wala font (NotoSansDevanagari) yahan reject hota hai.
    import glob
    for pat in patterns:
        for p in sorted(glob.glob(f"/usr/share/fonts/**/{pat}", recursive=True)):
            if _font_ok(p):
                print(f"[render] font auto-detected: {p}")
                return p
    raise FileNotFoundError(
        "Devanagari+Latin font nahi mila (A-D aur QUIZ PATHSHALA bhi chahiye).\n"
        "  Repo: kids-quiz-shorts/assets/fonts/Hind-Bold.ttf (SIL OFL)\n"
        "  System NotoSansDevanagari Latin glyphs nahi rakhta — use mat karo."
    )


FONT_BOLD = _pick(C.FONT_CANDIDATES,
                  ["Hind-Bold.ttf", "*Devanagari*Bold*.ttf", "Poppins-Bold.ttf",
                   "*Devanagari*.ttf", "Lohit-Devanagari.ttf"])
FONT_REG = _pick(C.FONT_CANDIDATES_REG,
                 ["Hind-Regular.ttf", "*Devanagari*Regular*.ttf", "Poppins-Medium.ttf",
                  "*Devanagari*.ttf", "Lohit-Devanagari.ttf"])
print(f"[render] font: {FONT_BOLD} (Devanagari+Latin)")
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


# Stroke SIRF glow layer par. Core par stroke mat lagana — Devanagari ke
# andar ke patle gaps (स, म, भ) bhar jaate hain aur akshar ek jaise dikhne
# lagte hain. Motai font SIZE se laate hain, stroke se nahi.
NEON_GLOW_STROKE = 3


def neon_text(img, xy, text, font, glow, core=None, pad=80):
    """Neon glow — blur ki kai layers ko ADDITIVELY jodo, phir upar crisp core.

    Pehle ye alpha_composite se ho raha tha, jisse glow bright hi nahi hota:
    alpha-over roshni ko jodta nahi, sirf dhak deta hai. Asli neon additive
    hota hai — isliye ImageChops.add.

    Core pura safed nahi rakha; glow rang ka halka tint hai, warna shabd ka
    rang wash out ho jaata hai aur sab safed dikhne lagta hai.

    Blur sirf shabd ke aas-paas ke box par lagta hai, poori 1080x1920 image
    par nahi — warna har shabd par 3 full-frame blur padte aur render kai
    guna dheema ho jaata.
    """
    d0 = ImageDraw.Draw(img)
    b = d0.textbbox(xy, text, font=font)
    box = (max(0, int(b[0]) - pad), max(0, int(b[1]) - pad),
           min(img.width, int(b[2]) + pad), min(img.height, int(b[3]) + pad))
    if box[2] <= box[0] or box[3] <= box[1]:
        return
    w, h = box[2] - box[0], box[3] - box[1]
    off = (xy[0] - box[0], xy[1] - box[1])

    # Glow bhi MOTE shape se banta hai, taaki halo akshar ke bahar rahe aur
    # patli jagahon (matra, sir-rekha) me ghus kar unhe na dhundhla kare.
    layer = Image.new("RGB", (w, h), (0, 0, 0))
    ImageDraw.Draw(layer).text(off, text, font=font, fill=glow,
                               stroke_width=NEON_GLOW_STROKE, stroke_fill=glow)

    region = img.crop(box).convert("RGB")
    # Sirf BAHAR ki do layers. Pehle ek 5px blur bhi tha jo glyph ke UPAR
    # baithta tha — usi se text dhundhla dikh raha tha. Neon me glow text ke
    # CHAARON OR hona chahiye, text ke upar nahi.
    # Halo ab door aur halka. Pehle 14px @0.85 abhi bhi glyph ke kinaron par
    # chadh raha tha, isliye text dhundhla lag raha tha.
    for radius, gain in ((34, 0.60), (18, 0.45)):
        blurred = layer.filter(ImageFilter.GaussianBlur(radius))
        if gain < 1:
            blurred = blurred.point(lambda v, g=gain: int(v * g))
        region = ImageChops.add(region, blurred)

    region = region.convert("RGBA")
    if core is None:
        # Core lagbhag safed — reference neon me bhi beech safed hota hai aur
        # rang kinaron/glow me. Halka tint (85% safed) rakha hai taaki shabd
        # ka rang phir bhi pehchana jaaye, par edge crisp rahe.
        core = tuple(min(255, int(c * 0.15 + 255 * 0.85)) for c in glow)
    # Core mota (stroke) — isse akshar glow ke beech se saaf ubhar aata hai
    # aur mobile pe 3 inch me bhi turant padha jaata hai.
    ImageDraw.Draw(region).text(off, text, font=font, fill=tuple(core) + (255,))
    img.paste(region, box)


def centered_multicolor(draw, lines, font, lh, cx, top, colors, img=None):
    """Har shabd alag rang me. Devanagari shaping shabd ke ANDAR hoti hai,
    space ke aar-paar nahi — isliye word-by-word draw karna surakshit hai.
    img diya ho aur NEON on ho to har shabd glow ke saath aata hai."""
    space = draw.textlength(" ", font=font)
    wi, y = 0, top
    for ln in lines:
        words = ln.split()
        widths = [draw.textlength(w, font=font) for w in words]
        total = sum(widths) + space * (len(words) - 1)
        x = cx - total / 2
        for w, wd in zip(words, widths):
            col = colors[wi % len(colors)]
            if C.NEON and img is not None:
                neon_text(img, (x, y), w, font, col)
            else:
                draw.text((x, y), w, font=font, fill=col)
            x += wd + space
            wi += 1
        y += lh
    return y


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
def banner(img, qnum=None, total=None, subject=None, hook=None):
    """Top ribbon + left me 'सवाल 1/2' chip. Right side timer ke liye khaali
    chhoda hai — isliye chip center me nahi hai.

    hook = pehle 1-2 second ki challenge line (sirf Q1 read segment). Frame 0
    par brand ka naam sirf jagah gherta tha — YouTube channel ka naam waise
    bhi neeche channel row me dikhata hai. Hook laal ribbon par, taaki timer
    shuru hote hi (brand wapas) ek visual badlaav bhi ho."""
    d = ImageDraw.Draw(img)
    text = C.BRAND
    fill = C.COLORS["banner"]
    if hook:
        for ch in EMOJI_STRIP:
            hook = hook.replace(ch, "")
        text = " ".join(hook.split())
        fill = C.COLORS["timer_ring"]
    d.rounded_rectangle([0, -60, C.W, 210], 60, fill=fill)
    f = F(78 if hook else 70)
    while text_w(d, text, f) > C.W - 120 and f.size > 44:
        f = F(f.size - 2)
    w = text_w(d, text, f)
    b = d.textbbox((0, 0), text, font=f)
    ty = 105 - (b[3] + b[1]) // 2 if hook else 62
    d.text(((C.W - w) // 2, ty), text, font=f,
           fill=(255, 255, 255) if hook else C.COLORS["banner_text"],
           stroke_width=3, stroke_fill=(90, 8, 42))
    # 1 sawaal wali video me "सवाल 1/1" bekaar hai — sirf subject chip dikhao
    if qnum and total > 1:
        chip = f"सवाल {qnum}/{total}"
        cf = F(46)
        cw = text_w(d, chip, cf)
        d.rounded_rectangle([70, 240, 70 + cw + 68, 336], 48,
                            fill=C.COLORS["card"] if C.NEON else (255, 255, 255),
                            outline=C.COLORS["banner_text"] if C.NEON else None,
                            width=3 if C.NEON else 0)
        d.text((104, 256), chip, font=cf,
               fill=C.COLORS["banner_text"] if C.NEON else C.COLORS["banner"])
    if subject:
        sf = F(44)
        sw = text_w(d, subject, sf)
        # Chip left me. Timer right me rehta hai, isliye takraav nahi hota.
        x0 = 70 if not (qnum and total > 1) else 70 + text_w(d, f"सवाल {qnum}/{total}", F(46)) + 92
        d.rounded_rectangle([x0, 244, x0 + sw + 60, 332], 44,
                            fill=C.COLORS["banner_text"])
        d.text((x0 + 30, 258), subject, font=sf, fill=C.COLORS["banner"])
    return img


# YouTube Shorts ka neeche ka UI lagbhag aakhri 250px dhak leta hai.
# FOOTER_Y ek ceiling hai: pill content ke neeche baithta hai, is line se
# neeche nahi, aur SAFE_BOTTOM se neeche koi zaroori cheez nahi.
FOOTER_Y = 1560
SAFE_BOTTOM = 1670       # 1920 - 250

# YouTube Shorts ka right action rail (like, dislike, comment, share, remix)
# video ke right kinare par, lagbhag beech se neeche tak rehta hai — 1080px
# wide frame me ~900px ke baad. Pehle options 1010px tak jaate the aur sahi
# jawab ka tick 930px par banta tha, yaani theek like/comment button ke
# peeche; viewer ko like button content me ghula hua dikhta tha.
# Isliye screen ke neeche wale hisse (options, इशारा, badge, footer) ka
# column COL_L se RAIL_X tak hai. Upar ka card aur timer rail se upar hain,
# wo poori width le sakte hain.
RAIL_X = 890             # is x ke right me (options ke level se neeche) kuch nahi
COL_L = 70
COL_CX = (COL_L + RAIL_X) // 2


EMOJI_STRIP = "👇👆✅❌🎯🔔🤔💡🔥"


def footer(img, text=None, y=FOOTER_Y, handle=False, after=None):
    """Screen text me emoji mat daalo — Poppins me emoji glyph nahi hai aur
    tofu box (□) render ho jaata hai. Option icons alag emoji font se aate hain.

    after = upar wale content ka bottom. FOOTER_Y ceiling hai, isliye lambe
    sawaal par footer UPAR khinch kar "सही जवाब!" badge ke upar chadh jaata
    tha. Ab jagah na ho to footer banta hi nahi — CTA pinned comment aur
    description me waise bhi hai."""
    d = ImageDraw.Draw(img)
    y = min(y, FOOTER_Y)          # safe zone se bahar kabhi nahi
    if after is not None and y < after + 12:
        return img
    t = text or C.CTA_TEXT
    for ch in EMOJI_STRIP:
        t = t.replace(ch, "")
    t = " ".join(t.split())
    f = F(44)
    w = text_w(d, t, f)
    pill = C.COLORS["card"] if C.NEON else (255, 255, 255)
    ink = C.COLORS["banner_text"] if C.NEON else C.COLORS["banner"]
    d.rounded_rectangle([COL_CX - w // 2 - 40, y, COL_CX + w // 2 + 40, y + 88],
                        44, fill=pill,
                        outline=ink if C.NEON else None, width=3 if C.NEON else 0)
    d.text((COL_CX - w // 2, y + 18), t, font=f, fill=ink)
    # Handle line hata di: wo 1584px par baithti thi (poori tarah YouTube ke
    # UI ke peeche) aur YouTube khud channel ka naam wahin dikhata hai —
    # duplicate tha. Chahiye to handle=True karo.
    if handle:
        hf = F(38, bold=False)
        hw = text_w(d, C.HANDLE, hf)
        d.text(((C.W - hw) // 2, y + 114), C.HANDLE, font=hf,
               fill=(255, 255, 255), stroke_width=2, stroke_fill=(60, 30, 90))
    return img


# Banner ke daayein hisse mein, card (y=348) se upar. r=104 taaki number
# feed mein turant dikhe. Last 3 second laal + moti ring.
TIMER_CX, TIMER_CY, TIMER_R = 910, 292, 108


def timer_ring(img, remaining, total):
    """Prominent countdown. remaining = float seconds."""
    d = ImageDraw.Draw(img)
    cx, cy, r = TIMER_CX, TIMER_CY, TIMER_R
    secs = max(0, math.ceil(remaining - 1e-6))
    urgent = secs <= 3
    ring = (220, 38, 38) if urgent else C.COLORS["timer_ring"]
    disc = (255, 236, 236) if urgent else (255, 255, 255)
    width = 28 if urgent else 22
    d.ellipse([cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14], fill=disc)
    box = [cx - r, cy - r, cx + r, cy + r]
    d.arc(box, 0, 360, fill=C.COLORS["timer_ring_bg"], width=width)
    frac = max(0.0, min(1.0, remaining / total))
    if frac > 0:
        d.arc(box, -90, -90 + 360 * frac, fill=ring, width=width)
    f = F(100 if not urgent else 112)
    s = str(secs)
    b = d.textbbox((0, 0), s, font=f)
    d.text((cx - (b[2] - b[0]) // 2 - b[0], cy - (b[3] - b[1]) // 2 - b[1] - 8),
           s, font=f, fill=ring)
    return img


# ---------------------------------------------------------------- panels
# Timer ring y~292 par hai. Sawaal uske neeche, phir bada visual (naksha ya
# icon), phir options. Neeche ~250px aur right rail khaali rehte hain.
QUESTION_TOP = 408
CARD_X = 58
CARD_MIN_H, CARD_MAX_H = 120, 156
OPT_H = 90
OPT_GAP = 8
OPT_PAD = 12
MAP_H = 460             # India ~1.07 tall/wide → silhouette still wider than 400px
ICON_INK = (14, 116, 144)


def visual_slot(after_y):
    """Map / icon card. Right edge RAIL_X se pehle. Ink width >= 400."""
    top = after_y + 14
    left, right = COL_L, RAIL_X - 16
    avail = right - left
    map_w = min(540, avail)
    x0 = left + (avail - map_w) // 2
    map_box = (x0, top, x0 + map_w, top + MAP_H)
    icon_box = (left, top, right, top + MAP_H)
    return {"map_box": map_box, "icon_box": icon_box, "bottom": top + MAP_H}


def _pictogram(q) -> str:
    blob = f"{q.get('q', '')} {q.get('sub', '')}"
    if any(k in blob for k in ("चाँद", "सूरज", "सूर्य", "ग्रह", "तारा")):
        return "sky"
    if any(k in blob for k in ("नदी", "समुद्र", "पानी", "झील")):
        return "water"
    if any(k in blob for k in ("जानवर", "पक्षी", "पशु", "मछली")):
        return "animal"
    return {
        "विज्ञान": "atom",
        "भारत": "tricolor",
        "दुनिया": "globe",
        "पहेली": "puzzle",
        "सामान्य ज्ञान": "bulb",
    }.get(q.get("sub") or "", "bulb")


def _icon_card(img, box, q):
    """Naksha na ho to bhi frame khaali na dikhe — subject ka icon card."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y0, x1, y1], 36, fill=(255, 255, 255))
    cx, cy = (x0 + x1) // 2, y0 + int((y1 - y0) * 0.40)
    kind = _pictogram(q)
    ink = ICON_INK
    r = 118
    if kind == "atom":
        d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=ink)
        d.ellipse([cx - r, cy - 46, cx + r, cy + 46], outline=ink, width=8)
        d.ellipse([cx - 46, cy - r, cx + 46, cy + r], outline=ink, width=8)
        d.arc([cx - r, cy - 70, cx + r, cy + 70], 20, 200, fill=ink, width=8)
    elif kind == "globe":
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ink, width=10)
        d.ellipse([cx - 52, cy - r, cx + 52, cy + r], outline=ink, width=8)
        d.arc([cx - r, cy - 48, cx + r, cy + 48], 0, 360, fill=ink, width=8)
        d.line([(cx - r, cy), (cx + r, cy)], fill=ink, width=8)
    elif kind == "tricolor":
        d.rounded_rectangle([cx - 130, cy - 90, cx + 130, cy - 30], 8, fill=(255, 153, 51))
        d.rounded_rectangle([cx - 130, cy - 30, cx + 130, cy + 30], 8, fill=(255, 255, 255),
                            outline=ink, width=4)
        d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], outline=ink, width=6)
        d.rounded_rectangle([cx - 130, cy + 30, cx + 130, cy + 90], 8, fill=(19, 136, 8))
    elif kind == "sky":
        d.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], fill=(255, 196, 64), outline=ink, width=8)
        for dx, dy, rr in ((-140, -40, 16), (120, -70, 12), (150, 30, 10), (-100, 80, 14)):
            d.ellipse([cx + dx - rr, cy + dy - rr, cx + dx + rr, cy + dy + rr], fill=ink)
    elif kind == "water":
        for i, dy in enumerate((-50, 10, 70)):
            d.arc([cx - 150, cy + dy - 40, cx + 150, cy + dy + 40], 200, 340, fill=ink, width=10)
    elif kind == "animal":
        d.ellipse([cx - 36, cy - 10, cx + 36, cy + 50], fill=ink)
        for dx, dy in ((-70, -20), (70, -20), (-28, -70), (28, -70)):
            d.ellipse([cx + dx - 28, cy + dy - 28, cx + dx + 28, cy + dy + 28], fill=ink)
    elif kind == "puzzle":
        mark = "?"
        mf = F(180)
        mb = d.textbbox((0, 0), mark, font=mf)
        d.text((cx - (mb[2] - mb[0]) // 2 - mb[0], cy - (mb[3] + mb[1]) // 2 - 10),
               mark, font=mf, fill=ink)
    else:
        d.ellipse([cx - 70, cy - 80, cx + 70, cy + 40], outline=ink, width=10)
        d.rounded_rectangle([cx - 28, cy + 36, cx + 28, cy + 78], 10, fill=ink)
        d.rectangle([cx - 46, cy + 78, cx + 46, cy + 100], fill=ink)
    sub = (q.get("sub") or "क्विज़").strip()
    sf = F(54)
    sw = text_w(d, sub, sf)
    d.text((cx - sw // 2, y1 - 120), sub, font=sf, fill=C.COLORS["q_text"])
    return img


def question_panel(q, qnum, total, highlight=None, dim_others=False,
                   show_options=4, hook=None):
    """show_options: kitne option dikhane hain (0-4).

    Shorts me sabse bada dushman STATIC screen hai. Pehle sawaal aur chaaron
    option ek saath aa jaate the aur phir 12 second tak kuch hilta hi nahi
    tha — viewer ke paas swipe karne ke alawa kuch bacha hi nahi tha. Ab
    option ek-ek karke aate hain, thik us waqt jab wo bole ja rahe hote hain.
    """
    """highlight=None -> normal. highlight=idx -> us option ko green.
    Ye base image hai; timer per-frame iske upar paste hota hai.
    Return: (image, options_block_end_y) — reveal badge/footer isi se position hote hain."""
    img = background(qnum).convert("RGB")
    banner(img, qnum, total, q.get("sub"), hook=hook)

    import indiamap
    states = indiamap.for_question(q)

    d = ImageDraw.Draw(img)
    inner_w = C.W - 2 * CARD_X - 80
    f, lines, lh = fit_lines(d, q["q"], inner_w, CARD_MAX_H - 64,
                             start=72, min_size=46, max_lines=3)
    card_h = max(CARD_MIN_H, min(CARD_MAX_H, len(lines) * lh + 64))
    card_box = [CARD_X, QUESTION_TOP, C.W - CARD_X, QUESTION_TOP + card_h]
    card(img, card_box, fill=C.COLORS["card"])

    d = ImageDraw.Draw(img)
    top = QUESTION_TOP + (card_h - len(lines) * lh) // 2
    if C.NEON:
        img = img.convert("RGBA")
        d = ImageDraw.Draw(img)
    centered_multicolor(d, lines, f, lh, C.W / 2, top,
                        [C.COLORS[k] for k in C.QUESTION_COLORS], img=img)
    slot = visual_slot(card_box[3])
    if states:
        correct = None
        if highlight is not None and 0 <= highlight < len(states):
            correct = states[highlight]
        indiamap.draw(
            img, slot["map_box"], [s for s in states if s], correct=correct,
        )
    else:
        _icon_card(img, slot["icon_box"], q)
    d = ImageDraw.Draw(img)

    opt_top = slot["bottom"] + OPT_PAD
    icons = icons_for(q)
    q_opts = q["opts"][:max(0, min(4, show_options))]
    text_x = 296 if icons else 206
    for i, opt in enumerate(q_opts):
        y = opt_top + i * (OPT_H + OPT_GAP)
        box = [COL_L, y, RAIL_X, y + OPT_H]
        is_hit = (highlight is not None and i == highlight)
        if is_hit:
            bg, fg, lab = C.COLORS["correct_bg"], C.COLORS["correct"], C.COLORS["correct"]
            d.rounded_rectangle(box, 34, fill=bg, outline=C.COLORS["correct"], width=8)
        else:
            faded = dim_others and highlight is not None
            # Faded rang theme ke hisaab se — dark mode me halka grey pill
            # bilkul toota hua dikhta hai.
            if faded:
                bg = (30, 22, 44) if C.NEON else (235, 235, 240)
            else:
                bg = C.COLORS["opt_bg"]
            # Har option ka apna rang — A neela, B hara, C laal, D purple
            dim_fg = (110, 96, 140) if C.NEON else (150, 150, 160)
            fg = (dim_fg if faded
                  else C.COLORS[C.OPTION_COLORS[i % len(C.OPTION_COLORS)]])
            lab = dim_fg if faded else C.COLORS["opt_label"]
            d.rounded_rectangle(box, 34, fill=bg,
                                outline=(70, 48, 110) if C.NEON else (220, 222, 235),
                                width=4)

        cx = 134
        d.ellipse([cx - 42, y + 14, cx + 42, y + OPT_H - 14],
                  fill=bg if C.NEON else (255, 255, 255), outline=lab, width=6)
        lf = F(58)
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

        of = F(64)
        max_w = RAIL_X - 110 - text_x      # 110 = tick ki jagah + padding
        while text_w(d, opt, of) > max_w and of.size > 34:
            of = F(of.size - 2)
        ob = d.textbbox((0, 0), opt, font=of)
        oy = y + OPT_H // 2 - (ob[3] + ob[1]) // 2
        if C.NEON and not (dim_others and not is_hit):
            neon_text(img, (text_x, oy), opt, of, fg)
        else:
            d.text((text_x, oy), opt, font=of, fill=fg)

        if is_hit:
            # Poppins me U+2713 glyph nahi hai (tofu box aata hai) -> haath se draw
            tx, ty = RAIL_X - 76, y + OPT_H // 2
            d.line([(tx - 26, ty + 2), (tx - 8, ty + 22), (tx + 28, ty - 24)],
                   fill=C.COLORS["correct"], width=11, joint="curve")

    opt_end = opt_top + 4 * (OPT_H + OPT_GAP) - OPT_GAP
    if highlight is None and opt_end + 100 < SAFE_BOTTOM:
        footer(img, "सोचिए…", y=opt_end + 18, after=opt_end)
    if img.mode == "RGBA":
        img = img.convert("RGB")
    return img, opt_end


def cta_panel(q, qnum, total):
    """Timer khatam, jawab abhi nahi. Options wahi rehte hain (viewer abhi bhi
    soch raha hai) aur upar se subscribe ka banner aata hai."""
    img, opt_end = question_panel(q, qnum, total)
    if getattr(C, "SUBSCRIBE_CTA", "end") != "before_answer":
        # 22-Sep ko bolne wali subscribe line hata di thi, par ye banner har
        # sawaal me reh gaya tha (2 sawaal = 2 baar). Ab default me subscribe
        # sirf aakhri reveal par (reveal_panel), yahan sirf intezaar ka pill.
        footer(img, "जवाब आ रहा है…", y=max(FOOTER_Y, opt_end + 34), after=opt_end)
        return img
    d = ImageDraw.Draw(img)
    t = "सब्सक्राइब करें"
    f = F(68)
    w = text_w(d, t, f)
    by = opt_end + 26
    d.rounded_rectangle([COL_CX - w // 2 - 52, by, COL_CX + w // 2 + 52, by + 104],
                        50, fill=C.COLORS["banner"], outline=C.COLORS["banner_text"],
                        width=6)
    d.text((COL_CX - w // 2, by + 16), t, font=f, fill=C.COLORS["banner_text"])
    footer(img, "जवाब आ रहा है…", y=max(FOOTER_Y, by + 140), after=by + 104)
    return img


def fauji_base(q, qnum, total):
    """Timer khatam: options wahi, neeche tiranga-rang ki patti, aur options ke
    khaali daayein hisse me fauji + jhanda (fauji_frame per-frame lagata hai).
    Return (image, region) — region = fauji ka box, like-rail (x>RAIL_X) se bahar."""
    img, opt_end = question_panel(q, qnum, total)
    d = ImageDraw.Draw(img)
    t = "सच्चे देशभक्त हो तो लाइक + सब्सक्राइब"
    f = F(56)
    while text_w(d, t, f) > RAIL_X - 80 - 100 and f.size > 36:
        f = F(f.size - 2)
    w = text_w(d, t, f)
    by = opt_end + 26
    d.rounded_rectangle([COL_CX - w // 2 - 44, by, COL_CX + w // 2 + 44, by + 96], 48,
                        fill=(255, 153, 51), outline=(19, 136, 8), width=7)
    d.text((COL_CX - w // 2, by + 14), t, font=f, fill=(255, 255, 255),
           stroke_width=3, stroke_fill=(120, 60, 0))
    # options ka text kahan tak jaata hai — fauji uske baad hi baithega
    icons = icons_for(q)
    text_x = 296 if icons else 206
    right = 0
    for opt in q["opts"]:
        of = F(64)
        while text_w(d, opt, of) > RAIL_X - 110 - text_x and of.size > 34:
            of = F(of.size - 2)
        right = max(right, text_x + text_w(d, opt, of))
    opt_top = opt_end - 4 * (OPT_H + OPT_GAP) + OPT_GAP
    x0 = min(max(right + 24, 520), RAIL_X - 250)
    return img, (x0, opt_top - 6, RAIL_X - 6, opt_end + 6)


def fauji_frame(base, region, t):
    """t = segment me seconds. Pehle 0.35s me fauji neeche se upar aata hai,
    jhanda poore time lehrata hai."""
    import fauji
    x0, y0, x1, y1 = region
    g = fauji.group(x1 - x0, y1 - y0, t)
    k = min(1.0, t / 0.35)
    ease = 1 - (1 - k) ** 3
    if k < 1:
        g.putalpha(g.getchannel("A").point(lambda a: int(a * ease)))
    img = base.copy()
    img.paste(g, (x0, y0 + int((1 - ease) * 120)), g)
    return img


def hint_panel(q, qnum, total):
    """Wajah dikhti hai, par sahi option abhi highlight NAHI hota — warna
    jawab yahin khul jaayega aur aakhri beat ka koi matlab nahi bachega."""
    img, opt_end = question_panel(q, qnum, total)
    d = ImageDraw.Draw(img)
    import tts as _tts
    why = (q.get("why") or "").strip()
    if why:
        why = _tts.mask_answer(why, q, "_____")
    y = opt_end + 20
    if why:
        # Options 1254px par khatam hote hain aur safe zone 1420 par. Yaani
        # ishara card ke paas sirf ~140px hai — isliye 2 line, chhota font,
        # aur kam padding. 3-4 line ka card seedha YouTube ke UI me ghus jaata tha.
        wf, wlines, wlh = fit_lines(d, why, RAIL_X - 80 - 80, 120, start=38,
                                    min_size=27, max_lines=2, bold=False)
        h = len(wlines) * wlh + 40
        top = y + 10
        d.rounded_rectangle([80, top, RAIL_X, top + h], 30,
                            fill=C.COLORS["card"] if C.NEON else (255, 255, 255),
                            outline=C.COLORS["timer_ring"], width=5)
        lf = F(34)
        bg_stroke = C.COLORS["bg_top"] if C.NEON else (255, 255, 255)
        d.text((116, top - 22), "इशारा", font=lf, fill=C.COLORS["timer_ring"],
               stroke_width=6, stroke_fill=bg_stroke)
        centered(d, wlines, wf, wlh, (80 + RAIL_X) // 2, top + 30, C.COLORS["opt_text"])
        y = top + h
    # Yahan footer chip NAHI. "इशारा" card khud hi message hai; ek aur chip
    # lagane se content safe zone (1420px) se bahar chala jaata tha.
    return img


def reveal_banner_text(qnum, total):
    """Reveal ke waqt top ribbon me kya likha ho (None = brand).

    Neeche jagah nahi hai: 4 option + "सही जवाब!" badge 1330px tak jaate hain
    aur safe zone 1420 par khatam — isliye reveal ka footer pill kabhi render
    hi nahi hota tha (CTA_TEXT chup-chaap drop). Top ribbon hamesha khaali hai.

    - Beech wala sawaal (Q1 of 2): "अगला सवाल…" teaser. Title me sirf Q1
      hota hai, isliye Q1 ka jawab milte hi log swipe kar dete the.
    - Aakhri sawaal + SUBSCRIBE_CTA="end": ek hi subscribe line — value dene
      ke BAAD, bina extra second aur bina bolne wali line ke."""
    if qnum < total and getattr(C, "NEXT_QUESTION_TEASER", True):
        return "रुकिए! अगला सवाल आ रहा है…"
    if qnum == total and getattr(C, "SUBSCRIBE_CTA", "end") == "end":
        return f"रोज़ {C.VIDEOS_PER_DAY} नए क्विज़ — सब्सक्राइब कीजिए"
    return None


_REVEAL_CACHE = {}


def _reveal_bases(q, qnum, total):
    key = (q.get("id"), qnum, total, q.get("ans"), bool(indiamap_states(q)))
    if key not in _REVEAL_CACHE:
        banner_hook = reveal_banner_text(qnum, total)
        plain, end_y = question_panel(q, qnum, total, hook=banner_hook)
        hit, end_y = question_panel(q, qnum, total, highlight=q["ans"], dim_others=True,
                                    hook=banner_hook)
        _REVEAL_CACHE[key] = (plain.convert("RGB"), hit.convert("RGB"), end_y)
    return _REVEAL_CACHE[key]


def indiamap_states(q):
    import indiamap
    return indiamap.for_question(q)


def _draw_reveal_overlay(img, q, opt_end, progress):
    """Badge scale-in, phir ek line ka kyun. progress 0..1."""
    p = max(0.0, min(1.0, progress))
    if p < 0.28:
        return img
    t = (p - 0.28) / 0.72
    d = ImageDraw.Draw(img)
    label = "सही जवाब!"
    f = F(58)
    w = text_w(d, label, f)
    by = min(opt_end + 12, SAFE_BOTTOM - 150)
    # halka scale: pill pehle patli, phir poori
    grow = 0.82 + 0.18 * min(1.0, t / 0.35)
    half = int((w // 2 + 40) * grow)
    top = by
    bot = by + int(76 * grow)
    d.rounded_rectangle([COL_CX - half, top, COL_CX + half, bot], 40, fill=C.COLORS["correct"])
    b = d.textbbox((0, 0), label, font=f)
    tw, th = b[2] - b[0], b[3] - b[1]
    d.text((COL_CX - tw // 2 - b[0], top + (bot - top - th) // 2 - b[1]),
           label, font=f, fill=(255, 255, 255))
    why = (q.get("why") or "").strip()
    room = SAFE_BOTTOM - (bot + 16)
    if why and p > 0.5 and room >= 64:
        wf, wlines, wlh = fit_lines(d, why, RAIL_X - COL_L - 64, room - 24,
                                    start=34, min_size=24, max_lines=2, bold=False)
        h = len(wlines[:2]) * wlh + 24
        y = bot + 10
        if y + h <= SAFE_BOTTOM:
            d.rounded_rectangle([COL_L, y, RAIL_X, y + h], 22, fill=(255, 255, 255),
                                outline=C.COLORS["correct"], width=4)
            centered(d, wlines[:2], wf, wlh, COL_CX, y + 12, C.COLORS["q_text"])
    return img


def reveal_at(q, qnum, total, progress):
    """Answer reveal animation. progress 0 = options plain, 1 = highlighted + kyun."""
    plain, hit, opt_end = _reveal_bases(q, qnum, total)
    p = max(0.0, min(1.0, float(progress)))
    blend = min(1.0, p / 0.4)
    img = Image.blend(plain, hit, blend)
    return _draw_reveal_overlay(img, q, opt_end, p)


def reveal_panel(q, qnum, total):
    return reveal_at(q, qnum, total, 1.0)


def hook_panel(line: str, question: str = ""):
    """Pehle ~2 second. Topic teaser + khud sawaal (jawab nahi)."""
    img = background(3).convert("RGB")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, -40, C.W, 200], 40, fill=C.COLORS["banner"])
    brand = C.BRAND
    bf = F(64)
    while text_w(d, brand, bf) > C.W - 140 and bf.size > 36:
        bf = F(bf.size - 2)
    bw = text_w(d, brand, bf)
    d.text(((C.W - bw) // 2, 58), brand, font=bf, fill=C.COLORS["banner_text"])

    text = " ".join((line or "").split())
    qtext = " ".join((question or "").split())
    card(img, [70, 240, C.W - 70, 700], fill=(255, 255, 255))
    d = ImageDraw.Draw(img)
    f, lines, lh = fit_lines(d, text, C.W - 220, 360, start=72, min_size=42, max_lines=4)
    top = 280 + (340 - len(lines) * lh) // 2
    centered(d, lines, f, lh, C.W // 2, top, C.COLORS["q_text"])
    if qtext:
        # Neeche ka card right rail se pehle rukta hai, aur khaali neeche
        # hissa bharata hai (safe zone ~1670).
        card(img, [COL_L, 740, RAIL_X, 1480], fill=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((COL_L + 36, 770), "सवाल", font=F(36), fill=C.COLORS["opt_label"])
        qf, qlines, qlh = fit_lines(d, qtext, RAIL_X - COL_L - 80, 520, start=68, min_size=42, max_lines=5)
        centered(d, qlines, qf, qlh, (COL_L + RAIL_X) // 2, 880, C.COLORS["q_text"])
    sub = f"{C.TIMER_SECONDS} सेकंड  ·  4 विकल्प"
    sf = F(42)
    sw = text_w(d, sub, sf)
    chip_y = 1520 if qtext else 1100
    cx = (COL_L + RAIL_X) // 2 if qtext else C.W // 2
    d.rounded_rectangle([cx - sw // 2 - 36, chip_y, cx + sw // 2 + 36, chip_y + 84],
                        36, fill=C.COLORS["timer_ring"])
    d.text((cx - sw // 2, chip_y + 14), sub, font=sf, fill=(255, 255, 255))
    return img


def comment_panel(questions=None):
    """Aakhri beat: comment CTA. Emoji alag font se, text Hind se."""
    img = background(5).convert("RGB")
    banner(img)
    d = ImageDraw.Draw(img)
    card(img, [COL_L, 420, RAIL_X, 1520], fill=(255, 255, 255))
    title = C.CTA_TEXT
    f, lines, lh = fit_lines(d, title, RAIL_X - COL_L - 80, 280, start=78, min_size=48, max_lines=3)
    y = centered(d, lines, f, lh, COL_CX, 560, C.COLORS["q_text"])
    tile = emoji_tile("👇", 160)
    if tile is not None:
        img.paste(tile, (COL_CX - 80, int(y) + 30), tile)
        y = int(y) + 210
    else:
        y = int(y) + 40
    hint = "A, B, C या D"
    hf = F(64)
    hw = text_w(d, hint, hf)
    d.text((COL_CX - hw // 2, y + 36), hint, font=hf, fill=C.COLORS["opt_label"])
    return img


def font_report() -> dict:
    latin = all(_glyph_real(FONT_BOLD, ch) for ch in "ABCDQUIZPATHSHALA")
    dev = _has_devanagari(FONT_BOLD)
    return {
        "font_path": FONT_BOLD,
        "font_latin": latin,
        "font_devanagari": dev,
        "timer_radius": TIMER_R,
        "option_font": 64,
    }


def assert_fonts():
    info = font_report()
    if not (info["font_latin"] and info["font_devanagari"]):
        raise SystemExit(f"[render] font coverage fail: {info}")
    print(f"[render] font OK latin+devanagari: {info['font_path']}")
    return info


def map_ink_width(img) -> int:
    """Cream/green silhouette ki chaudaai. Ocean tile nahi — khud desh."""
    import indiamap
    xs = []
    for y in range(480, 1400, 2):
        for x in range(40, RAIL_X, 2):
            px = img.getpixel((x, y))
            if px == indiamap.PLAIN_FILL or px == indiamap.ANSWER_FILL:
                xs.append(x)
    if not xs:
        return 0
    return max(xs) - min(xs)


def _map_ink(img) -> bool:
    return map_ink_width(img) >= 400


def visual_probe(questions) -> dict:
    """Gate ke liye kuch frames. Poori video nahi."""
    info = font_report()
    q = questions[0]
    hook_panel(C.HOOK_LINES["quiz"][0])
    import indiamap
    mapped = []
    for item in questions:
        panel, _ = question_panel(item, 1, max(2, len(questions)))
        if indiamap.for_question(item) and _map_ink(panel):
            mapped.append(item["id"])
    rev = reveal_at(q, 1, max(2, len(questions)), 1.0)
    comment_panel(questions)
    crop = rev.crop((COL_L, 1080, RAIL_X, SAFE_BOTTOM)).resize((48, 24))
    green = 0
    for px in crop.getdata():
        if px[1] > 120 and px[1] > px[0] + 20 and px[1] > px[2]:
            green += 1
    info.update({
        "why_on_reveal": bool((q.get("why") or "").strip()),
        "reveal_highlight": green > 3,
        "comment_cta": True,
        "map_ids": mapped,
    })
    return info


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
