"""Stage 5: Assemble the video.

v1 (this file): renders clean data CARDS from the shot list, times them to the
narration, lays the voiceover on top, burns captions. Produces a real, playable
mp4 so you can TEST the whole pipeline today.

Layout contract — the two text layers must never fight for the same pixels:

    y 0.00 - 0.08   channel label (muted, small)
    y 0.08 - 0.68   headline zone: the shot's on_screen_text, auto-sized to fit
    y 0.68 - 0.72   accent rule
    y 0.72 - 1.00   CAPTION ZONE — cards draw nothing here, burned-in only

Captions are written as .ass, not .srt: ffmpeg renders SRT against ASS's default
288px canvas and then upscales, so an SRT font size is roughly 3.75x larger than
it reads. Declaring PlayResX/Y makes the sizes below literal pixels.

UPGRADE PATH: replace _make_card() with real assets — pull stock footage via each
shot's source_asset_query (PEXELS_API_KEY is already in .env) and render real
charts with matplotlib. The timing, caption, and audio-mux logic stays the same.
"""
import json, pathlib, re, shutil, subprocess
from PIL import Image, ImageDraw, ImageFont
from common import cfg, read, ok, die, RUN, ROOT

W, H = 1920, 1080
BG = (14, 17, 22)
FG = (235, 235, 235)
ACCENT = (245, 197, 66)
MUTED = (110, 118, 130)

CAPTION_TOP = 0.72          # cards must not draw below this
SIDE_MARGIN = 150
CAPTION_WORDS = 6           # words per caption cue

FONT_CANDIDATES = [
    ROOT / "assets/fonts/Inter-Bold.ttf",
    ROOT / "assets/fonts/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
_font_cache = {}


def _font(size):
    if size in _font_cache:
        return _font_cache[size]
    for p in FONT_CANDIDATES:
        try:
            if pathlib.Path(p).exists():
                f = ImageFont.truetype(str(p), size)
                _font_cache[size] = f
                return f
        except OSError:
            continue
    try:
        f = ImageFont.load_default(size=size)
    except TypeError:
        f = ImageFont.load_default()
    _font_cache[size] = f
    return f


def _fit(d, text, max_w, max_h, hi=400, lo=48, gap=1.18):
    """Shrink until the wrapped text fits the box. Headlines vary from '72' to a
    full sentence, so a fixed size either clips the long ones or wastes the short."""
    size = hi
    while size >= lo:
        f = _font(size)
        lines, cur = [], ""
        for word in text.split():
            trial = f"{cur} {word}".strip()
            if d.textlength(trial, font=f) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        line_h = size * gap
        if len(lines) * line_h <= max_h and all(d.textlength(l, font=f) <= max_w for l in lines):
            return f, lines, line_h
        size -= 8
    f = _font(lo)
    return f, text.split()[:6], lo * gap


def _make_card(shot, idx, total, channel):
    """v1: a data card. Renders ONLY the headline the Visual Agent marked for
    screen — visual_description is a production note for sourcing footage and
    must never be shown to a viewer."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # channel label, top-left
    if channel and not str(channel).startswith("TODO"):
        d.text((SIDE_MARGIN, 56), str(channel).upper(), font=_font(30), fill=MUTED)

    headline = str(shot.get("on_screen_text") or "").strip()
    if headline.lower() == "null":
        headline = ""

    if headline:
        box_top, box_bottom = int(H * 0.14), int(H * 0.64)
        f, lines, line_h = _fit(d, headline, W - 2 * SIDE_MARGIN, box_bottom - box_top)
        y = box_top + ((box_bottom - box_top) - len(lines) * line_h) / 2
        for line in lines:
            w = d.textlength(line, font=f)
            d.text(((W - w) / 2, y), line, font=f, fill=ACCENT)
            y += line_h
        # accent rule under the headline, still above the caption zone
        rule_y = int(H * 0.685)
        d.rectangle([W // 2 - 90, rule_y, W // 2 + 90, rule_y + 5], fill=ACCENT)

    # progress bar
    frac = (idx + 1) / max(total, 1)
    d.rectangle([0, H - 7, int(W * frac), H], fill=ACCENT)

    p = RUN / f"card_{idx:03d}.png"
    img.save(p)
    return p


def _ass_time(sec):
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _cues(text, start, end, max_words=CAPTION_WORDS):
    """Split a shot's spoken line into short cues spread across its duration.
    Dumping a whole 20-word sentence on screen for 6 seconds is unreadable."""
    words = str(text or "").split()
    if not words:
        return []
    groups = [words[i:i + max_words] for i in range(0, len(words), max_words)]
    span = max(0.4, float(end) - float(start))
    t = float(start)
    out = []
    for g in groups:
        share = span * (len(g) / len(words))
        out.append((t, t + share, " ".join(g)))
        t += share
    return out


ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial,58,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,160,160,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ass_escape(text):
    return re.sub(r"\s+", " ", str(text)).replace("{", "(").replace("}", ")").strip()


def _require_ffmpeg():
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            die(f"{tool} not found on PATH. Install FFmpeg and re-run.\n"
                f"  Windows: winget install Gyan.FFmpeg   (then open a new terminal)\n"
                f"  macOS:   brew install ffmpeg\n"
                f"  Linux:   sudo apt-get install ffmpeg")


def _audio_seconds(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def main():
    c = cfg()
    _require_ffmpeg()

    plan = json.loads(read("shots.json"))
    shots = plan.get("shots") or []
    if not shots:
        die("No shots in shots.json")
    voice = RUN / "voice.mp3"
    if not voice.exists():
        die("run/voice.mp3 missing — run run_voice.py first.")

    # 1) rescale estimated shot timings onto the real narration length
    audio_dur = _audio_seconds(voice)
    planned = max(float(s["end_sec"]) for s in shots)
    scale = audio_dur / planned if planned > 0 else 1.0
    ok(f"narration {audio_dur:.1f}s vs planned {planned:.1f}s — scaling timings x{scale:.3f}")
    for s in shots:
        s["start_sec"] = float(s["start_sec"]) * scale
        s["end_sec"] = float(s["end_sec"]) * scale

    # 2) cards + concat list + captions
    channel = c["channel"].get("name", "")
    concat, events = [], []
    for i, shot in enumerate(shots):
        dur = max(0.5, float(shot["end_sec"]) - float(shot["start_sec"]))
        card = _make_card(shot, i, len(shots), channel)
        concat.append(f"file '{card.name}'\nduration {dur:.3f}")
        for start, end, text in _cues(shot.get("spoken_line"), shot["start_sec"], shot["end_sec"]):
            events.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Cap,,0,0,0,,{_ass_escape(text)}")
    concat.append(f"file '{(RUN / f'card_{len(shots)-1:03d}.png').name}'")

    (RUN / "concat.txt").write_text("\n".join(concat), encoding="utf-8")
    (RUN / "subs.ass").write_text(ASS_HEADER + "\n".join(events) + "\n", encoding="utf-8")
    ok(f"built {len(shots)} cards + {len(events)} caption cues")

    # 3) images -> silent video
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
        "-fps_mode", "vfr", "-pix_fmt", "yuv420p", "silent.mp4"
    ], cwd=RUN, check=True)

    # 4) voiceover + burned captions -> final.mp4
    #
    # fps= MUST come before ass=. silent.mp4 is variable-frame-rate with one frame
    # per card, so burning captions straight onto it gives the filter only 18 frames
    # to draw on — every caption would freeze until the next card change. Resampling
    # to the target rate first gives each caption its own frames.
    fps = str(c["video"]["fps"])
    subprocess.run([
        "ffmpeg", "-y", "-i", "silent.mp4", "-i", "voice.mp3",
        "-vf", f"fps={fps},ass=subs.ass",
        "-r", fps, "-fps_mode", "cfr",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "final.mp4"
    ], cwd=RUN, check=True)

    ok(f"wrote run/final.mp4 ({audio_dur/60:.1f} min)")


if __name__ == "__main__":
    main()
