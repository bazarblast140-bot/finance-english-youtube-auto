"""Channel identity: the permanent intro and the thumbnail.

The intro is the same every video, so it is rendered once and cached in assets/.
The cache key is a hash of the name, tagline and duration — change any of them in
config.json and the next run rebuilds it without being asked.

The intro is composed frame by frame in PIL rather than as an ffmpeg filtergraph.
It is built once, so the slower path costs nothing, and typing + a drawn underline
+ a fading tagline is far easier to get right in code than in nested expressions.
"""
import hashlib, pathlib, shutil, subprocess

from PIL import Image, ImageDraw, ImageFont

import sketch
from common import ROOT, RUN, ok

W, H = 1920, 1080
ASSETS = ROOT / "assets"

FONTS = [
    ASSETS / "fonts/Inter-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
_cache = {}


def font(size):
    size = int(size)
    if size not in _cache:
        for p in FONTS:
            try:
                if pathlib.Path(p).exists():
                    _cache[size] = ImageFont.truetype(str(p), size)
                    break
            except OSError:
                continue
        else:
            try:
                _cache[size] = ImageFont.load_default(size=size)
            except TypeError:
                _cache[size] = ImageFont.load_default()
    return _cache[size]


def _ease(t):
    """Ease-out — linear motion reads as mechanical."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _fit_width(text, target, hi, lo=40):
    """Largest size at which text still fits the target width."""
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    size = hi
    while size > lo and probe.textlength(text, font=font(size)) > target:
        size -= 4
    return font(size)


def _intro_frame(i, total, name, tagline, fps):
    """One intro frame. Timeline over `total` frames:
        0.10-1.60s  name types in, cursor leads
        1.70-2.30s  accent rule draws under it
        2.20-3.10s  tagline fades up
        last 0.35s  everything fades to black for the cut
    """
    t = i / fps
    img = Image.new("RGB", (W, H), sketch.PAPER)
    d = ImageDraw.Draw(img)

    f_name = _fit_width(name, W - 460, 190, 70)
    name_w = d.textlength(name, font=f_name)
    nx, ny = (W - name_w) / 2, H * 0.34

    # type the name
    type_start, type_len = 0.10, 1.50
    shown = name
    if t < type_start:
        shown = ""
    elif t < type_start + type_len:
        frac = (t - type_start) / type_len
        shown = name[:max(0, int(len(name) * frac))]
    if shown:
        d.text((nx, ny), shown, font=f_name, fill=sketch.INK)

    # cursor leads the text while typing, then blinks twice and leaves
    if type_start <= t < type_start + type_len + 0.5:
        cx = nx + d.textlength(shown, font=f_name) + 8
        blink = t >= type_start + type_len and int((t - type_start) * 6) % 2 == 1
        if not blink:
            bbox = f_name.getbbox("H")
            d.rectangle([cx, ny + bbox[1], cx + 10, ny + bbox[3]], fill=sketch.HIGHLIGHT)

    # hand-drawn rule under the name
    if t >= 1.70:
        grow = _ease((t - 1.70) / 0.60)
        if grow > 0.02:
            y = ny + f_name.size * 1.30
            sketch.rough_underline(d, nx, nx + name_w * grow, y, sketch.HIGHLIGHT, 9, seed=4)

    # tagline fades up into place
    if tagline and t >= 2.20:
        a = _ease((t - 2.20) / 0.85)
        f_tag = _fit_width(tagline, W - 560, 62, 30)
        tw = d.textlength(tagline, font=f_tag)
        lift = int(24 * (1 - a))
        shade = tuple(int(sketch.PAPER[c] + (sketch.COOL[c] - sketch.PAPER[c]) * a) for c in range(3))
        d.text(((W - tw) / 2, ny + f_name.size * 1.75 + lift), tagline, font=f_tag, fill=shade)

    # fade out so the cut into the hook is not abrupt
    total_s = total / fps
    if t > total_s - 0.35:
        k = min(1.0, (t - (total_s - 0.35)) / 0.35)
        img = Image.blend(img, Image.new("RGB", (W, H), (0, 0, 0)), k)
    return img


def intro_clip(cfg_dict, fps, x264_args, force=False):
    """Render (or reuse) the permanent intro. Returns a Path, or None if disabled.

    x264_args must match the shot clips exactly — the clips are joined with
    `concat -c copy`, which refuses streams whose encoder parameters differ.
    """
    brand = cfg_dict.get("branding", {})
    seconds = float(brand.get("intro_seconds", 0) or 0)
    if seconds <= 0:
        return None

    name = str(cfg_dict["channel"].get("name", "")).strip()
    tagline = str(cfg_dict["channel"].get("tagline", "")).strip()
    if not name or name.startswith("TODO"):
        return None

    key = hashlib.sha1(f"{name}|{tagline}|{seconds}|{fps}|{x264_args}".encode()).hexdigest()[:10]
    dest = ASSETS / f"intro-{key}.mp4"
    if dest.exists() and not force:
        return dest

    # drop stale intros so assets/ does not collect one per edit
    for old in ASSETS.glob("intro-*.mp4"):
        old.unlink(missing_ok=True)

    tmp = RUN / "_intro"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)

    total = int(seconds * fps)
    for i in range(total):
        _intro_frame(i, total, name, tagline, fps).save(tmp / f"f{i:04d}.png")

    subprocess.run(
        ["ffmpeg", "-y", "-framerate", str(fps), "-i", "f%04d.png",
         "-r", str(fps), *x264_args, str(dest.resolve())],
        cwd=tmp, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(tmp, ignore_errors=True)
    ok(f"built intro ({seconds:.0f}s) -> {dest.name}")
    return dest


# --------------------------------------------------------------------------

def _pick_shot(shots):
    """The thumbnail wants the punchiest frame, not the first one: a short
    headline with a highlight reads at phone size; a full sentence does not."""
    def score(s):
        head = str(s.get("on_screen_text") or "")
        if not head:
            return -999
        v = 100 - len(head) * 2
        if s.get("highlight"):
            v += 30
        if any(ch.isdigit() for ch in head):
            v += 25
        return v
    return max(shots, key=score) if shots else None


def thumbnail(cfg_dict, shots, path, tw=1280, th=720):
    """1280x720 thumbnail built from the video's strongest shot."""
    shot = _pick_shot(shots)
    if shot is None:
        return None

    img = Image.new("RGB", (tw, th), sketch.PAPER)

    # reuse the shot's own footage as the backdrop, heavily darkened
    src = shot.get("_backdrop")
    if src and pathlib.Path(src).exists():
        grab = RUN / "_thumb_src.jpg"
        try:
            subprocess.run(["ffmpeg", "-y", "-ss", "1", "-i", str(src), "-frames:v", "1",
                            "-vf", f"scale={tw}:{th}:force_original_aspect_ratio=increase,"
                                   f"crop={tw}:{th}", "-q:v", "3", str(grab)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with Image.open(grab) as bg:
                # Heavy: stock clips often contain their own text or numbers, and
                # a glittering "10" behind a headline that says 72 is worse than
                # no backdrop at all. It is texture, not content.
                img = Image.blend(bg.convert("RGB"), Image.new("RGB", (tw, th), sketch.PAPER), 0.76)
        except (subprocess.CalledProcessError, OSError):
            pass

    # vignette so the centre carries the eye
    vig = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    for k in range(60):
        a = int(120 * (k / 60) ** 2)
        vd.rectangle([-k * 14, -k * 9, tw + k * 14, th + k * 9], outline=(0, 0, 0, a), width=14)
    img = Image.alpha_composite(img.convert("RGBA"), vig).convert("RGB")

    d = ImageDraw.Draw(img)
    head = str(shot.get("on_screen_text")).strip()

    # Grow to fill, don't shrink to fit: a thumbnail is judged at ~320px wide in
    # the feed, so the headline has to dominate the frame.
    max_w, max_h = tw - 120, th * 0.66
    size, f, lines = 60, font(60), [head]
    for probe in range(400, 48, -6):
        pf = font(probe)
        words, ls, cur = head.split(), [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if d.textlength(trial, font=pf) <= max_w or not cur:
                cur = trial
            else:
                ls.append(cur)
                cur = w
        if cur:
            ls.append(cur)
        if len(ls) <= 3 and len(ls) * probe * 1.14 <= max_h \
                and all(d.textlength(l, font=pf) <= max_w for l in ls):
            size, f, lines = probe, pf, ls
            break

    line_h = size * 1.14
    y = (th - len(lines) * line_h) / 2 - 24
    hl = str(shot.get("highlight") or "").strip()

    layer = img.convert("RGBA")
    for i, line in enumerate(lines):
        pos = line.lower().find(hl.lower()) if hl and hl.lower() != "null" else -1
        lx = (tw - d.textlength(line, font=f)) / 2
        if pos >= 0:
            x = lx + d.textlength(line[:pos], font=f)
            b = ImageDraw.Draw(layer).textbbox((x, y + i * line_h), line[pos:pos + len(hl)], font=f)
            layer.alpha_composite(sketch.marker_highlight(
                (tw, th), (b[0] - 10, b[1] - 10, b[2] + 10, b[3] + 10), sketch.HIGHLIGHT, seed=2))
    img = layer.convert("RGB")
    d = ImageDraw.Draw(img)

    for i, line in enumerate(lines):
        lx = (tw - d.textlength(line, font=f)) / 2
        ly = y + i * line_h
        d.text((lx, ly), line, font=f, fill=sketch.INK, stroke_width=6, stroke_fill=(0, 0, 0))
        pos = line.lower().find(hl.lower()) if hl and hl.lower() != "null" else -1
        if pos >= 0:
            d.text((lx + d.textlength(line[:pos], font=f), ly), line[pos:pos + len(hl)],
                   font=f, fill=sketch.PAPER)

    name = str(cfg_dict["channel"].get("name", "")).strip()
    if name and not name.startswith("TODO"):
        fn = font(38)
        d.text((54, th - 74), name.upper(), font=fn, fill=sketch.HIGHLIGHT)

    img.save(path, quality=92)
    return path
