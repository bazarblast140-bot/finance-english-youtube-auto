"""Preflight: fail fast on setup problems BEFORE burning API credits.

Runs first in run_pipeline.py. Can also be run alone:  python check_setup.py
"""
import os, shutil, sys
from common import cfg, ROOT, ok

def main():
    problems, warnings = [], []
    c = cfg()

    # --- secrets ---
    llm_provider = c["models"].get("llm_provider", "anthropic")
    if not (ROOT / ".env").exists() and not os.environ.get(f"{llm_provider.upper()}_API_KEY"):
        problems.append("No .env file. Copy .env.example to .env and fill in your keys.")
    if llm_provider == "kimi":
        if not os.environ.get("KIMI_API_KEY"):
            problems.append("KIMI_API_KEY not set (.env or environment).")
        if not os.environ.get("KIMI_BASE_URL"):
            problems.append("KIMI_BASE_URL not set (.env or environment).")
    elif not os.environ.get("ANTHROPIC_API_KEY"):
        problems.append("ANTHROPIC_API_KEY not set (.env or environment).")
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        if not os.environ.get(key):
            warnings.append(f"{key} not set — report will print to console instead of Telegram.")

    # --- config TODOs ---
    if str(c["channel"]["name"]).startswith("TODO"):
        warnings.append("config.json -> channel.name is still TODO.")

    # --- voice engine (only ElevenLabs needs a key) ---
    engine = c["voice"].get("engine", "edge").lower()
    if engine == "elevenlabs":
        if not os.environ.get("ELEVENLABS_API_KEY"):
            problems.append("voice.engine is 'elevenlabs' but ELEVENLABS_API_KEY is not set.")
        if str(c["voice"]["voice_id"]).startswith("TODO"):
            problems.append("voice.engine is 'elevenlabs' but voice.voice_id is still TODO.")
    elif engine == "edge":
        try:
            __import__("edge_tts")
        except ImportError:
            problems.append("voice.engine is 'edge' but edge-tts is not installed. "
                            "Run: pip install -r requirements.txt")
    else:
        problems.append(f"config.json -> voice.engine '{engine}' unknown (use 'edge' or 'elevenlabs').")

    # --- binaries ---
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            problems.append(f"{tool} not on PATH. Windows: winget install Gyan.FFmpeg "
                            "(then open a NEW terminal). macOS: brew install ffmpeg.")

    # --- python deps ---
    for mod, pkg in (("anthropic", "anthropic"), ("requests", "requests"), ("PIL", "Pillow")):
        try:
            __import__(mod)
        except ImportError:
            problems.append(f"Python package missing: {pkg}. Run: pip install -r requirements.txt")

    # --- topics left ---
    try:
        import json
        bank = json.loads((ROOT / "topic_bank.json").read_text(encoding="utf-8"))
        left = sum(1 for t in bank["topics"] if not t["used"])
        if left == 0:
            problems.append("topic_bank.json has no unused topics left. Add more.")
        elif left <= 3:
            warnings.append(f"Only {left} unused topic(s) left in topic_bank.json.")
    except (OSError, ValueError, KeyError) as e:
        problems.append(f"topic_bank.json unreadable: {e}")

    # --- fonts (cosmetic) ---
    fonts = list((ROOT / "assets/fonts").glob("*.ttf")) if (ROOT / "assets/fonts").exists() else []
    if not fonts and not os.path.exists("C:/Windows/Fonts/segoeuib.ttf"):
        warnings.append("No TTF in assets/fonts — cards will use a fallback font.")

    for w in warnings:
        print(f"[warn] {w}")
    if problems:
        print("\n[FAIL] Preflight found blocking problems:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)

    ok(f"preflight passed{' with ' + str(len(warnings)) + ' warning(s)' if warnings else ''}")

if __name__ == "__main__":
    main()
