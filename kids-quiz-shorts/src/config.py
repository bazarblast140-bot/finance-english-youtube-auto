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
TARGET_SECONDS = 55.0   # 2 sawaal ke liye thoda upar (pehle 32 tha 1 sawaal ke liye)

# Jawab se pehle: salute karta fauji + lehrata tiranga + "सच्चे देशभक्त हैं तो
# लाइक-सब्सक्राइब… जवाब अभी बताती हूँ" (Rajesh, 13-Sep-2026).
# 22-Sep-2026: band kiya — repetitive engagement-bait signal impressions
# throttle kar sakta hai. False = normal CTA_TEXT use hota hai.
FAUJI_CTA = False
# "इशारा" segment jawab se pehle. Fauji "जवाब अभी बताती हूँ" bolta hai — uske
# baad ishara aaye to wada toot-ta hai aur video lamba hota hai, isliye band.
HINT_BEFORE_ANSWER = False

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
# !! RISK (30-Sep-2026 review) !! Ye sirf "grey area" nahi hai:
#   - README, purane tags ("hindi riddles for class 1 to 5"), hooks
#     ("स्कूल जाने से पहले", "90% बच्चे...") aur cartoon-style design sab
#     bacchon ko target karte dikhte the. YouTube ke rule me label CONTENT
#     aur INTENDED AUDIENCE se tay hota hai, creator ki marzi se nahi.
#     YouTube khud video ko "made for kids" set kar sakta hai, aur galat
#     label par channel pe action / FTC (COPPA) penalty ka risk hai.
#   - Is PR ne kids-signal wale tags/hooks hata diye hain taaki metadata
#     "general Hindi GK (teens + adults, competitive exam)" wale pivot se
#     match kare. Par ASLI faisla Rajesh ka hai — code ye flag chupke se
#     nahi badalta. Dekho README "Made for Kids" section.
#   - True karne ka asar: comments band, pinned comment nahi, personalized
#     ads nahi (RPM kam), notification bell / Shorts remix jaise features
#     band. Monetization (YPP) phir bhi possible hai.
# Channel-level "audience" setting (YouTube Studio > Settings > Channel >
# Advanced) bhi isi ke saath match rakhna.
MADE_FOR_KIDS = False

CTA_TEXT = ("घर में सबको ये सवाल पूछो!" if MADE_FOR_KIDS
            else "जवाब कमेंट में लिखो 👇")

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
# kaafi tez hai (video 54s -> 40s). Saaf aur aaram se bolti awaaz chahiye,
# isliye wapas normal speed.
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
VIDEOS_PER_DAY = len(SLOT_ORDER)
PAHELI_SUB = "पहेली"


# ---------- growth knobs (30-Sep-2026 review) ----------
# Pehle 1-2 second ka ON-SCREEN hook. Sirf Q1 ke "read" segment me:
#   - top banner me brand ki jagah challenge line (brand YouTube khud
#     channel row me dikhata hai, frame 0 par wo jagah bekaar thi)
#   - "ध्यान से सुनिए…" pill ki jagah bada challenge pill
# Voice / timing nahi badalti — sawaal frame 0 se hi bolna shuru hota hai.
# Line sach honi chahiye: nakli "90% log galat" statistics nahi.
HOOK_ON_SCREEN = True
HOOK_LINES = {
    "quiz":   ["8 सेकंड में जवाब दो!", "सोचो, फिर बताओ!", "ये आता है आपको?",
               "आज का GK चैलेंज", "पक्का पता है?"],
    "paheli": ["बूझो तो जानें!", "8 सेकंड में बूझो!", "दिमाग़ लगाओ!",
               "आज की पहेली"],
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
ACTIVE_SLOTS = [s.strip() for s in os.getenv("QUIZ_ACTIVE_SLOTS", "").split(",")
                if s.strip()] or list(SLOT_ORDER)
