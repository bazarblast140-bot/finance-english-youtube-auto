"""Stage 5: Assemble the video.

v1 (this file): renders clean text/data CARDS from the shot list, times them to the
shot list, lays the voiceover on top, burns subtitles. Produces a real, playable mp4
so you can TEST the whole pipeline today.

Shot timings from the Visual Agent are ESTIMATES (150 wpm). The real narration is
never exactly that long, so timings are rescaled to the actual voice.mp3 duration —
otherwise subtitles drift by 10+ seconds by the end of an 8-minute video.

UPGRADE PATH (marked TODO below): replace _make_card() with real assets —
pull stock footage via source_asset_query, render real charts with matplotlib.
The timing/subtitle/mux logic stays the same.
"""
import json, pathlib, shutil, subprocess, textwrap
from PIL import Image, ImageDraw, ImageFont
from common import cfg, read, ok, die, RUN, ROOT

W, H = 1920, 1080
BG = (14, 17, 22)        # dark
FG = (235, 235, 235)
ACCENT = (245, 197, 66)  # amber
MUTED = (120, 128, 140)

FONT_CANDIDATES = [
    ROOT / "assets/fonts/Inter-Bold.ttf",
    ROOT / "assets/fonts/DejaVuSans-Bold.ttf",
    # system fallbacks so cards look right even with an empty assets/fonts
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

def _font(size):
    for p in FONT_CANDIDATES:
        try:
            if pathlib.Path(p).exists():
                return ImageFont.truetype(str(p), size)
        except OSError:
            continue
    # Pillow >= 10.1 can scale the built-in font; older versions give a fixed
    # tiny bitmap (readable-ish, but install a TTF for real output).
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()

def _draw_centered(d, lines, font, y, fill, line_h):
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((W - w) / 2, y), ln, font=font, fill=fill)
        y += line_h
    return y

def _make_card(shot, idx, total):
    """v1: text/data card. TODO: swap for real stock footage / matplotlib charts."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    ost = shot.get("on_screen_text")
    if ost and str(ost).lower() != "null":
        # headline number / overlay — the thing Gate 3 guarantees is on screen
        f = _font(120)
        lines = textwrap.wrap(str(ost), width=18)[:4]
        y = H // 2 - (len(lines) * 150) // 2 - 40
        y = _draw_centered(d, lines, f, y, ACCENT, 150)
        # supporting context under the number
        desc = str(shot.get("visual_description", ""))[:90]
        if desc:
            _draw_centered(d, textwrap.wrap(desc, width=52)[:2], _font(44), y + 30, MUTED, 58)
    else:
        f = _font(64)
        lines = textwrap.wrap(str(shot.get("visual_description", "")), width=30)[:5]
        y = H // 2 - (len(lines) * 80) // 2
        _draw_centered(d, lines, f, y, FG, 80)

    # subtle progress bar so long videos feel like they're moving
    frac = (idx + 1) / max(total, 1)
    d.rectangle([0, H - 8, int(W * frac), H], fill=ACCENT)

    p = RUN / f"card_{idx:03d}.png"
    img.save(p)
    return p

def _srt_time(sec):
    sec = max(0.0, float(sec))
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60); ms = int(round((sec - int(sec)) * 1000))
    if ms == 1000:  # rounding carry
        s, ms = s + 1, 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

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

    # 2) build cards + an ffmpeg concat list + subtitles
    concat, srt = [], []
    for i, shot in enumerate(shots):
        dur = max(0.5, float(shot["end_sec"]) - float(shot["start_sec"]))
        card = _make_card(shot, i, len(shots))
        concat.append(f"file '{card.name}'\nduration {dur:.3f}")
        line = "\n".join(textwrap.wrap(str(shot.get("spoken_line", "")).strip(), width=52)[:2])
        srt.append(f"{i+1}\n{_srt_time(shot['start_sec'])} --> {_srt_time(shot['end_sec'])}\n{line}\n")
    # ffmpeg concat needs the last image repeated to honour its duration
    concat.append(f"file '{(RUN / f'card_{len(shots)-1:03d}.png').name}'")
    (RUN / "concat.txt").write_text("\n".join(concat), encoding="utf-8")
    (RUN / "subs.srt").write_text("\n".join(srt), encoding="utf-8")
    ok(f"built {len(shots)} cards + subtitles")

    # 3) images -> silent video
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
        "-fps_mode", "vfr", "-pix_fmt", "yuv420p", "silent.mp4"
    ], cwd=RUN, check=True)

    # 4) add voiceover + burn subtitles -> final.mp4
    fps = str(c["video"]["fps"])
    style = "FontSize=44,PrimaryColour=&Hffffff&,OutlineColour=&H90000000&,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=70"
    subprocess.run([
        "ffmpeg", "-y", "-i", "silent.mp4", "-i", "voice.mp3",
        "-vf", f"subtitles=subs.srt:force_style='{style}'",
        "-r", fps, "-fps_mode", "cfr",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "final.mp4"
    ], cwd=RUN, check=True)

    ok(f"wrote run/final.mp4 ({audio_dur/60:.1f} min)")

if __name__ == "__main__":
    main()
