"""Ek jagah pe saare knobs. Baaki koi file me hardcode mat karna."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"
ASSETS = ROOT / "assets"
OUT.mkdir(exist_ok=True)

# ---------- video ----------
W, H = 1080, 1920           # YouTube Shorts vertical
FPS = 30
QUESTIONS_PER_VIDEO = 2     # Rajesh spec: 2 sawaal per short
TIMER_SECONDS = 8           # Rajesh spec: 8 second tik-tik
INTRO_SECONDS = 2.0
REVEAL_SECONDS = 3.2
OUTRO_SECONDS = 3.0
READ_PAD_SECONDS = 0.6      # voice khatam hone ke baad thoda gap

# ---------- brand ----------
BRAND = "Bacchon Ka GK"
HANDLE = "@bacchonkagk"

# ---------- COPPA / Made for Kids ----------
# Rajesh ne False choose kiya taaki comments chaalu rahein (engagement CTA
# kaam kare, aur personalized ads se RPM bacha rahe).
#
# Iska matlab: tum YouTube ko bata rahe ho ki ye video bacchon ke liye
# "directed" NAHI hai — audience parents/teachers hai jo bacchon ko padhate
# hain. Content khud bacchon ke syllabus ka hai, isliye ye grey area hai.
# Ye compliance call tumhara hai. Galat label pe FTC/YouTube action ka risk
# rehta hai. Channel-level "audience" setting bhi isi ke saath match rakhna.
MADE_FOR_KIDS = False

CTA_TEXT = ("घर में सबको ये सवाल पूछो!" if MADE_FOR_KIDS
            else "सही जवाब कमेंट में लिखो!")

# Kids palette — high contrast, thumbnail-safe (rajesh-ui-pro: bold > subtle for Shorts)
COLORS = {
    "bg_top":     (255, 214, 102),   # warm yellow
    "bg_bottom":  (255, 138, 76),    # orange
    "card":       (255, 255, 255),
    "card_shadow": (0, 0, 0, 60),
    "q_text":     (26, 32, 84),      # deep indigo
    "opt_text":   (32, 38, 60),
    "opt_label":  (214, 40, 57),     # red A/B/C/D
    "opt_bg":     (245, 247, 255),
    "correct":    (24, 168, 88),
    "correct_bg": (222, 250, 233),
    "timer_ring": (214, 40, 57),
    "timer_ring_bg": (232, 232, 240),
    "banner":     (176, 20, 80),
    "banner_text": (255, 224, 92),
    "footer":     (60, 60, 80),
}

FONT_CANDIDATES = [
    str(ASSETS / "fonts" / "NotoSansDevanagari-Bold.ttf"),
    "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
FONT_CANDIDATES_REG = [
    str(ASSETS / "fonts" / "NotoSansDevanagari-Regular.ttf"),
    "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
    "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]

# ---------- audio ----------
SAMPLE_RATE = 44100
TICK_VOLUME = 0.30
VOICE_VOLUME = 1.0

# ---------- ElevenLabs ----------
# Voice ID env se aata hai — female Hindi voice jo tumne set ki hai.
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVEN_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
ELEVEN_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
ELEVEN_STABILITY = 0.45
ELEVEN_SIMILARITY = 0.80
ELEVEN_SPEED = 1.0

# Fallback agar ElevenLabs fail ho (quota/network): edge-tts female Hindi
EDGE_VOICE = os.getenv("EDGE_VOICE", "hi-IN-SwaraNeural")

# ---------- scheduling ----------
# GitHub Actions me UTC cron use hota hai; ye sirf metadata/labelling ke liye.
SLOTS = {"morning": "07:30 IST", "evening": "18:30 IST"}
