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
QUESTIONS_PER_VIDEO = 1     # 1 sawaal = ~25s video. Top Hindi GK shorts
                            # 16-30s ke hote hain; 50s wale pe log swipe kar dete hain.
TIMER_SECONDS = 8           # Rajesh spec: 8 second tik-tik
# Length ke do alag number hain — inhe mat mila dena:
#   HARD_LIMIT_SECONDS = platform ka asli rule. Oct 2024 se Shorts 3 MINUTE
#     tak ke ho sakte hain (pehle 60s tha). Isse upar gaya to normal video
#     ban jaata hai, Shorts feed me nahi jaata.
#   TARGET_SECONDS = retention ka target, rule nahi. Shorts ka engagement
#     sweet spot 30-60s hai, isliye hum yahin rehne ki koshish karte hain.
HARD_LIMIT_SECONDS = 180.0
TARGET_SECONDS = 32.0   # ab 1 sawaal hai, video 25-30s me aani chahiye

INTRO_SECONDS = 2.0
REVEAL_SECONDS = 3.2
OUTRO_SECONDS = 3.0
READ_PAD_SECONDS = 0.6      # voice khatam hone ke baad thoda gap

# ---------- brand ----------
BRAND = "QUIZ PATHSHALA"
HANDLE = "@QuizPathshalaIndia"

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
            else "जवाब कमेंट में लिखो 👇")

# Kids palette — high contrast, thumbnail-safe (rajesh-ui-pro: bold > subtle for Shorts)
# Palette channel branding se match ki hai — purple banner, yellow accent,
# white "?" logo. Shorts feed me channel avatar aur video ek hi family lagein.
COLORS = {
    "bg_top":     (124, 58, 237),    # violet-600
    "bg_bottom":  (167, 139, 250),   # violet-400
    "card":       (255, 255, 255),
    "card_shadow": (0, 0, 0, 60),
    "q_text":     (46, 16, 101),     # violet-950
    "opt_text":   (39, 27, 72),
    "opt_label":  (124, 58, 237),    # violet A/B/C/D
    "opt_bg":     (247, 245, 255),
    "correct":    (22, 163, 74),
    "correct_bg": (220, 252, 231),
    "timer_ring": (245, 158, 11),    # amber — purple pe sabse zyada pop karta hai
    "timer_ring_bg": (233, 228, 245),
    "banner":     (76, 29, 149),     # violet-900
    "banner_text": (253, 224, 71),   # yellow-300, banner ke Hindi text jaisa
    "footer":     (60, 60, 80),

    # Multi-colour text — Hindi GK shorts ka standard look. Ye rang SIRF
    # safed card par use hote hain, isliye contrast ki dikkat nahi.
    "word1": (198, 40, 40),     # gehra laal
    "word2": (21, 101, 192),    # gehra neela
    "word3": (46, 125, 50),     # gehra hara
    "word4": (74, 20, 140),     # brand purple
}

# Question ke words in rango me ghoomte hain; har option ka apna rang.
QUESTION_COLORS = ["word1", "word2", "word3", "word4"]
OPTION_COLORS = ["word2", "word3", "word1", "word4"]

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
TICK_VOLUME = 0.20   # voice ab timer ke dauran chalti hai, tick dabna nahi chahiye
VOICE_VOLUME = 1.0

# ---------- ElevenLabs ----------
# Voice ID env se aata hai — female Hindi voice jo tumne set ki hai.
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVEN_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
ELEVEN_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
ELEVEN_STABILITY = 0.45
ELEVEN_SIMILARITY = 0.80
# 1.08 sirf isliye rakha tha ki video 60s ke andar aa jaye — par wo "limit"
# thi hi nahi (asli limit 3 min hai), aur ElevenLabs edge-tts se waise hi
# kaafi tez hai (video 54s -> 40s). Class 1-5 ke bacchon ko saaf aur thodi
# aaram se bolti awaaz chahiye, isliye wapas normal speed.
ELEVEN_SPEED = 1.0

# Fallback agar ElevenLabs fail ho (quota/network): edge-tts female Hindi
EDGE_VOICE = os.getenv("EDGE_VOICE", "hi-IN-SwaraNeural")

# ---------- scheduling ----------
# GitHub Actions me UTC cron use hota hai; ye sirf metadata/labelling ke liye.
# 5 video roz. Time bacchon ki availability ke hisaab se chuna hai:
#   morning  — school jaane se pehle
#   noon     — lunch / ghar pe
#   paheli   — school ke baad, riddle (search + family time)
#   evening  — homework se pehle
#   night    — khaane ke baad, family time
SLOT_ORDER = ["morning", "noon", "paheli", "evening", "night"]
QUIZ_SLOTS = ["morning", "noon", "evening", "night"]  # 4 subject-rotate; paheli alag
SLOTS = {
    "morning": "07:30 IST",
    "noon":    "13:30 IST",
    "paheli":  "16:00 IST",
    "evening": "17:30 IST",
    "night":   "20:30 IST",
}
VIDEOS_PER_DAY = len(SLOT_ORDER)
PAHELI_SUB = "पहेली"
