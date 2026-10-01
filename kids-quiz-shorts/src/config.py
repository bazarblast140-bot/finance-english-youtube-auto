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
QUESTIONS_PER_VIDEO = 2     # 2 sawaal ek Short me. Pehle 1 tha (~25s).
                            # Ab: Q1 (read+timer+answer) → Q2 (read+timer+answer)
                            # Total ~50-65s, Shorts limit (3 min) ke andar.
TIMER_SECONDS = 8           # Rajesh spec: 8 second tik-tik
# Length ke do alag number hain — inhe mat mila dena:
#   HARD_LIMIT_SECONDS = platform ka asli rule. Oct 2024 se Shorts 3 MINUTE
#     tak ke ho sakte hain (pehle 60s tha). Isse upar gaya to normal video
#     ban jaata hai, Shorts feed me nahi jaata.
#   TARGET_SECONDS = retention ka target, rule nahi. Shorts ka engagement
#     sweet spot 30-60s hai, isliye hum yahin rehne ki koshish karte hain.
HARD_LIMIT_SECONDS = 180.0
TARGET_SECONDS = 38.0   # retention window ~30-40s (2 sawaal + hook + end CTA)
LENGTH_MIN_SECONDS = 30.0
LENGTH_MAX_SECONDS = 40.0
HOOK_SECONDS = 2.0          # pehle 2 second: challenge on screen + voice
COMMENT_CTA_SECONDS = 2.2   # aakhri beat: comment CTA

# Jawab se pehle: salute karta fauji + lehrata tiranga + "सच्चे देशभक्त हैं तो
# लाइक-सब्सक्राइब… जवाब अभी बताती हूँ" (Rajesh, 13-Sep-2026).
# 22-Sep-2026: band kiya — repetitive engagement-bait signal impressions
# throttle kar sakta hai. False = normal CTA_TEXT use hota hai.
FAUJI_CTA = False
# "इशारा" segment jawab se pehle. Fauji "जवाब अभी बताती हूँ" bolta hai — uske
# baad ishara aaye to wada toot-ta hai aur video lamba hota hai, isliye band.
HINT_BEFORE_ANSWER = False

INTRO_SECONDS = 2.0
REVEAL_SECONDS = 3.6        # jawab + on-screen kyun padhne ki fursat
OUTRO_SECONDS = 3.0
READ_PAD_SECONDS = 0.28     # voice ke baad chhota gap — 30-40s window ke liye

# ---------- brand ----------
BRAND = "QUIZ PATHSHALA"
HANDLE = "@QuizPathshalaIndia"

# ---------- Audience / Made for Kids ----------
# FAISLA (Rajesh, 01-Oct-2026): QUIZ PATHSHALA kids channel NAHI hai.
# Audience = general: teens, adults, competitive-exam (SSC/Railway/Police)
# aur GK fans. Isliye MADE_FOR_KIDS = False rehta hai, aur content, metadata,
# hooks aur design me bacchon/school wala koi signal nahi hona chahiye
# (tests/test_growth.py ye check karta hai). Sawaal exam-GK level ke hon,
# aur bhasha "आप" wali (कीजिए/लिखिए), "तुम/तू" wali nahi.
# Channel-level audience setting (YouTube Studio > Settings > Channel >
# Advanced) bhi "No, it's not made for kids" hi rakhni hai.
MADE_FOR_KIDS = False

# On-screen string mein emoji mat daalo — 👇 alag emoji font se paste hota hai.
# "आप" register: कीजिए, करो nahi.
CTA_TEXT = "अपना जवाब कमेंट कीजिए"
COMMENT_CTA_VOICE = "अपना जवाब कमेंट कीजिए।"

# Palette — high contrast, mobile pe 3 inch me turant padha jaana chahiye
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

# ---------- NEON mode ----------
# BAND. Glow ke saath text ke aas-paas hamesha halka dhundhlapan reh jaata
# tha — Devanagari ki matra aur sir-rekha patli hoti hain, unke upar koi bhi
# blur turant chipak jaata hai. Shorts me 8 second me padhna hota hai,
# isliye chamak se zyada saaf dikhna zaroori hai.
#
# Ab: solid background, SAFED boxes, aur box par gehre rang ka text.
# Yahi format Hindi GK shorts me sabse zyada chalta hai kyunki contrast
# sabse zyada milta hai.
NEON = False

COLORS.update({
    "bg_top":        (46, 26, 71),      # #2E1A47
    "bg_bottom":     (46, 26, 71),      # flat — koi gradient nahi
    "card":          (255, 255, 255),   # sawaal aur options, dono ek hi rang
    "opt_bg":        (255, 255, 255),
    "opt_text":      (39, 27, 72),
    "q_text":        (26, 16, 54),
    "opt_label":     (46, 26, 71),
    "banner":        (26, 14, 44),      # bg se thoda gehra
    "banner_text":   (253, 224, 71),    # yellow
    "correct":       (22, 163, 74),
    "correct_bg":    (214, 250, 227),
    "timer_ring":    (229, 57, 53),     # laal — safed ring par sabse alert
    "timer_ring_bg": (228, 224, 238),
    # Safed box par gehre rang — teeno me contrast 7:1 se upar hai
    "word1": (198, 40, 40),     # gehra laal
    "word2": (21, 101, 192),    # gehra neela
    "word3": (27, 94, 32),      # gehra hara
    "word4": (69, 39, 160),     # gehra purple
})

QUESTION_COLORS = ["word1", "word2", "word3", "word4"]
OPTION_COLORS = ["word2", "word3", "word1", "word4"]

# Hind (SIL OFL) Devanagari + Latin dono cover karta hai. System ka
# NotoSansDevanagari Bold Latin (A-D, QUIZ PATHSHALA) render NAHI karta —
# isliye vendored Hind pehle, aur picker Latin glyphs maangta hai.
FONT_CANDIDATES = [
    str(ASSETS / "fonts" / "Hind-Bold.ttf"),
    str(ASSETS / "fonts" / "NotoSansDevanagari-Bold.ttf"),
    "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
FONT_CANDIDATES_REG = [
    str(ASSETS / "fonts" / "Hind-Regular.ttf"),
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
# kaafi tez hai (video 54s -> 40s). Saaf aur aaram se bolti awaaz chahiye,
# isliye wapas normal speed.
ELEVEN_SPEED = 1.0

# Fallback agar ElevenLabs fail ho (quota/network): edge-tts female Hindi
EDGE_VOICE = os.getenv("EDGE_VOICE", "hi-IN-SwaraNeural")

# ---------- scheduling ----------
# GitHub Actions me UTC cron use hota hai; ye sirf metadata/labelling ke liye.
# 5 video roz (QUIZ_ACTIVE_SLOTS se kam kar sakte ho). General audience ke
# daily routine ke hisaab se:
#   morning  — subah ki chai / commute
#   noon     — lunch break
#   paheli   — shaam se pehle, riddle
#   evening  — office / padhai ke baad
#   night    — khaane ke baad
SLOT_ORDER = ["morning", "noon", "paheli", "evening", "night"]

# 22-Sep-2026: paheli wapas 1/din kiya.
# 10-Sep se 3/din test kiya tha (morning + paheli + night). Analytics (24 Aug–21 Sep)
# dikha: 11 Sep ke baad impressions collapse (200-700 → 32) aur views single digits.
# Retention theek raha → distribution throttle, content quality nahi.
# Ab PAHELI_SLOTS = ["paheli"] only. Baaki 4 slots subject-rotate (variety).
# 7 din monitor karenge (pre-11 Sep baseline: ~400-1300 views/day).
#
# Slot ke NAAM waise ke waise hain (workflow ka cron mapping inhi par tika
# hai) — sirf unme kya content jaata hai wo badla hai.
PAHELI_SLOTS = ["paheli"]
QUIZ_SLOTS = ["morning", "noon", "evening", "night"]  # subject-rotate; variety
SLOTS = {
    "morning": "07:30 IST",
    "noon":    "13:30 IST",
    "paheli":  "16:00 IST",
    "evening": "17:30 IST",
    "night":   "20:30 IST",
}
PAHELI_SUB = "पहेली"


# ---------- growth knobs (30-Sep-2026 review) ----------
# Pehle 2 second: alag hook segment. On-screen badi line + wahi line voice mein.
# Seed = date + slot + pehle sawaal ki id, taaki videos ek jaise na khulen.
# Line sach honi chahiye: nakli "90% log galat" statistics nahi.
# Register "आप" (दीजिए / बताइए / सोचिए). Tum-imperative (करो/बताओ) nahi.
HOOK_ON_SCREEN = True
HOOK_LINES = {
    "quiz":   ["8 सेकंड में जवाब दीजिए!", "सोचिए, फिर बताइए!", "ये आता है आपको?",
               "पक्का पता है आपको?", "तैयार हैं आप?", "चुनिए — ए, बी, सी या डी",
               "आज का GK चैलेंज", "दिमाग़ लगाइए!", "क्या आप बता सकते हैं?",
               "जवाब दीजिए, 8 सेकंड हैं"],
    "paheli": ["बूझिए तो जानें!", "8 सेकंड में बूझिए!", "दिमाग़ लगाइए!",
               "आज की पहेली", "ये पहेली सुलझेगी?", "सोचिए, फिर बूझिए!"],
}
# Q1 ka jawab aane ke baad viewer swipe kar deta hai (Q2 title me hai hi
# nahi). Isliye Q1 reveal par "अगला सवाल…" teaser — open loop, zero seconds.
NEXT_QUESTION_TEASER = True
# Subscribe CTA:
#   "end"           -> sirf AAKHRI reveal par ek chhota visual pill (value dene
#                      ke baad, koi extra second nahi, koi bolne wali line nahi)
#   "before_answer" -> purana: har sawaal me jawab se pehle "सब्सक्राइब करें"
#                      banner (22-Sep ko voice hata di thi par banner reh gaya tha)
#   "off"           -> kahin nahi
SUBSCRIBE_CTA = os.getenv("QUIZ_SUBSCRIBE_CTA", "end")

# Repeat control (pick.py). Pehle paheli pool khatam hote hi poore riddle
# bank se RANDOM uthata tha — "एक थाली में सौ मोती" 3 din me do baar gaya.
# Ab: fresh pehle, phir sabse PURANA use hua (least-recently-used). Cooldown
# se kam purana sawaal tabhi aata hai jab aur koi rasta na ho (aur log me
# WARNING aati hai).
REPEAT_COOLDOWN_DAYS = 30
BANK_LOW_DAYS = 7          # itne din se kam ka fresh stock bacha to WARNING

# Kaunse slot sach me banenge. Default sab 5. GitHub repo variable
# QUIZ_ACTIVE_SLOTS="morning,paheli,night" set karo to baaki slot ke run
# bina upload ke skip ho jaate hain — workflow file edit kiye bina
# upload frequency kam/zyada kar sakte ho.
ACTIVE_SLOTS = [s for s in SLOT_ORDER
                if s in {x.strip() for x in os.getenv("QUIZ_ACTIVE_SLOTS", "").split(",")}] \
    or list(SLOT_ORDER)
# Description / CTA me "रोज़ N नए सवाल" — active slots ke hisaab se sach rahe
VIDEOS_PER_DAY = len(ACTIVE_SLOTS)

# Quality gate (src/quality.py). Fact check: secret DEEPSEEK_API_KEY.
QUALITY_HISTORY = DATA / "quality_history.jsonl"
TRENDS_PATH = DATA / "trends.json"
