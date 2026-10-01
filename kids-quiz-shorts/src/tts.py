"""Voice engine.

Order: ElevenLabs (primary, tumhari female Hindi voice) -> edge-tts (hi-IN-SwaraNeural)
-> silent track (pipeline kabhi crash na ho, video phir bhi bane).

Har call ka output ek WAV file + uska exact duration, kyunki render.py ko
timing chahiye segment length set karne ke liye.
"""
import hashlib
import json
import re
import subprocess
import shutil
from pathlib import Path

import config as C

CACHE = C.OUT / "voice_cache"
CACHE.mkdir(exist_ok=True, parents=True)

# Auth ek baar fail ho gaya to har line pe dobara try karne ka koi matlab nahi —
# ek hi run me 7 identical error aate the. Ab pehli baar pe hi haar maan lete hain.
_eleven_dead = False


# ---------------------------------------------------------------- helpers
def audio_duration(path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(r.stdout)["format"]["duration"])


def _to_wav(src, dst):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src),
         "-ar", str(C.SAMPLE_RATE), "-ac", "1", str(dst)],
        check=True,
    )
    return dst


from numwords import speak_numbers


def clean_for_tts(text: str) -> str:
    """TTS ko emoji/symbols mat do — Swara aur ElevenLabs dono unko literal padh
    dete hain ya glitch karte hain."""
    drop = "🔥✅❌👉🎯⭐️*#_~`|<>[]{}"
    for ch in drop:
        text = text.replace(ch, " ")
    text = text.replace("?", "? ").replace("।", "। ")
    # ₹ ko ElevenLabs "Rs" bolta hai: "₹500" -> "500 रुपये", akela ₹ (जैसे "चिन्ह ₹ किस") hatao.
    # "9:15" -> "9 बजकर 15 मिनट" (warna "नौ:पंद्रह" jaata tha).
    text = re.sub(r"(?:₹|\bRs\.?)\s?(\d[\d,]*(?:\.\d+)?)(\s*(?:करोड़|लाख|हज़ार|हजार))?", r"\1\2 रुपये", text)
    text = re.sub(r"₹|\bRs\b\.?", " ", text)
    text = re.sub(r"\b(\d{1,2}):([0-5]\d)\b", r"\1 बजकर \2 मिनट", text)
    # Ank ko Hindi shabd me badlo. ElevenLabs digits theek nahi padhti —
    # "1853" ko galat ya ek-ek ank karke bol deti hai. Screen par digits
    # waise hi rehte hain, ye sirf bolne wale text par lagta hai.
    text = speak_numbers(text)
    return " ".join(text.split())


# ---------------------------------------------------------------- engines
def _eleven(text: str, out_wav: Path) -> bool:
    global _eleven_dead
    if _eleven_dead:
        return False
    if not (C.ELEVEN_API_KEY and C.ELEVEN_VOICE_ID):
        return False
    if not C.ELEVEN_API_KEY.startswith("sk_"):
        # Sabse common galti: dashboard se key ka *ID* copy kar lena. Asli key
        # sirf banate/rotate karte waqt ek baar dikhti hai aur 'sk_' se shuru hoti hai.
        print("[tts] ElevenLabs key 'sk_' se shuru nahi hoti — lagta hai key ID "
              "copy ho gaya hai, asli API key nahi. Free voice pe chal rahe hain.")
        _eleven_dead = True
        return False
    try:
        import requests
    except ImportError:
        return False
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{C.ELEVEN_VOICE_ID}"
    headers = {"xi-api-key": C.ELEVEN_API_KEY,
               "Content-Type": "application/json",
               "Accept": "audio/mpeg"}

    def payload(with_speed: bool):
        vs = {"stability": C.ELEVEN_STABILITY,
              "similarity_boost": C.ELEVEN_SIMILARITY}
        if with_speed:
            vs["speed"] = C.ELEVEN_SPEED
        return {"text": text, "model_id": C.ELEVEN_MODEL, "voice_settings": vs}

    try:
        r = requests.post(url, headers=headers, json=payload(True), timeout=90)
        # "speed" har model/plan pe supported nahi hai — 422 aata hai. Us case me
        # bina speed ke dobara try karo, warna poori voice hi free fallback pe
        # chali jaati hai sirf ek optional parameter ki wajah se.
        if r.status_code == 422:
            print(f"[tts] ElevenLabs 422 (speed unsupported?) — bina speed retry: "
                  f"{r.text[:160]}")
            r = requests.post(url, headers=headers, json=payload(False), timeout=90)
        if r.status_code != 200:
            print(f"[tts] ElevenLabs FAIL {r.status_code}: {r.text[:300]}")
            if r.status_code in (400, 401, 403):     # auth/quota — retry bekaar
                _eleven_dead = True
            return False
        mp3 = out_wav.with_suffix(".mp3")
        mp3.write_bytes(r.content)
        _to_wav(mp3, out_wav)
        mp3.unlink(missing_ok=True)
        return True
    except Exception as e:
        print(f"[tts] ElevenLabs failed: {e}")
        return False


def _edge(text: str, out_wav: Path) -> bool:
    if not shutil.which("edge-tts"):
        return False
    try:
        mp3 = out_wav.with_suffix(".mp3")
        subprocess.run(
            ["edge-tts", "--voice", C.EDGE_VOICE, "--text", text,
             "--write-media", str(mp3)],
            check=True, capture_output=True,
        )
        _to_wav(mp3, out_wav)
        mp3.unlink(missing_ok=True)
        return True
    except Exception as e:
        print(f"[tts] edge-tts failed: {e}")
        return False


def _silent(text: str, out_wav: Path) -> bool:
    """Aakhri fallback. Duration estimate asli TTS ke kareeb rakha hai —
    pehle 2.6 words/sec tha, jisse local dry-run 56s dikhata tha jabki asli
    edge-tts video 77s ka bana. Measured rate ~1.9 words/sec hai."""
    words = max(len(text.split()), 1)
    dur = max(1.5, words / 1.9)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"anullsrc=r={C.SAMPLE_RATE}:cl=mono",
         "-t", f"{dur:.2f}", str(out_wav)],
        check=True,
    )
    print(f"[tts] SILENT fallback used ({dur:.1f}s) — voice missing!")
    return True


# ---------------------------------------------------------------- public
def say(text: str, tag: str = "") -> tuple[Path, float, str]:
    """Returns (wav_path, duration_seconds, engine_used). Cached by text hash."""
    text = clean_for_tts(text)
    key = hashlib.sha1(
        f"{text}|{C.ELEVEN_VOICE_ID}|{C.ELEVEN_MODEL}".encode()
    ).hexdigest()[:16]
    out_wav = CACHE / f"{tag}_{key}.wav" if tag else CACHE / f"{key}.wav"
    meta = out_wav.with_suffix(".json")

    if out_wav.exists() and meta.exists():
        m = json.loads(meta.read_text())
        return out_wav, m["dur"], m["engine"] + "+cache"

    for name, fn in (("elevenlabs", _eleven), ("edge", _edge), ("silent", _silent)):
        if fn(text, out_wav):
            dur = audio_duration(out_wav)
            meta.write_text(json.dumps({"dur": dur, "engine": name, "text": text}))
            return out_wav, dur, name
    raise RuntimeError("Koi TTS engine kaam nahi kiya")


def question_script(q: dict, index: int, total: int) -> str:
    """Sirf sawaal — koi lead-in nahi ("पहला सवाल" waghairah hata diya).

    Shorts me viewer scroll karke aata hai; pehle 1-2 second me agar sawaal
    shuru nahi hua to wo aage scroll kar deta hai. Isliye frame 0 se hi
    sawaal bolna shuru hota hai.

    Options alag se bolte hain — wo timer ke DAURAN chalte hain."""
    if q.get("sub") == "पहेली":
        return f"पहेली। {q['q']}"
    return q["q"]


def options_script(q: dict) -> str:
    """Timer chalte waqt bolne ke liye — chaaron option."""
    labels = ["ए", "बी", "सी", "डी"]
    opts = "। ".join(f"{labels[i]}, {o}" for i, o in enumerate(q["opts"]))
    return f"{opts}। सोचिए।"


_DEVA_WORD = r"[\u0900-\u097F\w]"
# Hindi me shabd ka roop badalta hai: "कछुआ" -> "कछुए", "गाय" -> "गायों".
_SUFFIXES = ("ों", "ें", "ों", "े", "ए", "ओं", "ी", "ं")


def _variants(word: str):
    """Jawab ke shabd ke aam inflected roop (sabse lambe pehle)."""
    out = {word}
    for end in ("ा", "आ"):
        if word.endswith(end):
            stem = word[: -len(end)]
            out |= {stem + "े", stem + "ए", stem + "ों", stem + "ओं"}
    out |= {word + suf for suf in _SUFFIXES}
    return sorted(out, key=len, reverse=True)


def mask_answer(why: str, q: dict, blank: str) -> str:
    """Hint me se jawab ka naam hata do.

    Zyadatar 'why' lines jawab ke naam se hi shuru hoti hain
    ("प्रशांत महासागर धरती से bada hai") — agar aise hi bol diya to hint hi
    jawab de deta hai aur aakhri beat bekaar ho jaati hai.

    01-Oct-2026 fix: pehle sirf 3+ akshar wale shabd chhupte the, isliye
    "11 खिलाड़ी", "52 हफ़्ते", "मकड़ी के 8" jaise chhote/number jawab hint me
    seedhe bol diye jaate the; "कछुए" (कछुआ ka roop) aur "सात" (7 shabdon me)
    bhi bach jaate the; aur "गायों" -> "येों", "सरदार वल्लभभाई पटेल" -> "ये ये ने"
    jaise toote vaakya bante the. Ab: poora shabd (word boundary) match,
    inflected roop, number shabdon me bhi, aur lagatar "ये ये" ek ho jaata hai."""
    ans = q["opts"][q["ans"]].strip()
    digits = ans.replace(",", "").replace(" ", "")
    is_num = digits.isdigit()
    # Numeric jawab (saal, sankhya) ko "ये" se badalne par vaakya toot jaata
    # hai — "16 अप्रैल 1853 को" banta tha "सोलह अप्रैल ये को". Aise me shabd
    # ko hata dena behtar padhta hai: "सोलह अप्रैल को".
    if blank == "ये" and is_num:
        blank = ""
    words = [w for w in ans.split() if w != ans]
    if any(ch.isdigit() for ch in ans):
        # "1.3 सेकंड" -> sirf number chhupao; "सेकंड" jaise unit shabd har
        # jagah se gayab hoke vaakya tod dete the.
        words = [w for w in words if w[0].isdigit()]
    else:
        # chhote jod-shabd ("में", "जब", "एक") multi-word jawab me mat chhupao
        words = [w for w in words if len(w) >= 3]
    targets = [ans] + words
    if is_num:
        n = int(digits)
        targets.append(digits)
        try:
            from numwords import number_words
            targets.append(number_words(n))
        except Exception:  # noqa: BLE001 — number shabd optional
            pass
    out = why
    for t in targets:
        t = t.strip("()'\"")
        if not t:
            continue
        for v in _variants(t) if not t[0].isdigit() else [t]:
            pat = rf"(?<!{_DEVA_WORD}){re.escape(v)}(?!{_DEVA_WORD})"
            if v[0].isdigit():
                pat = rf"(?<![\d.,]){re.escape(v)}(?![\d.,]*\d)"
            # number tukda ("26 जनवरी" ka "26") -> hata do; "ये जनवरी" bura padhta hai
            out = re.sub(pat, "" if (v[0].isdigit() and t != ans) else blank, out)
    out = " ".join(out.split())
    if blank:
        out = re.sub(rf"(?:{re.escape(blank)}\s+)+{re.escape(blank)}(?!{_DEVA_WORD})", blank, out)
    # Mask ke baad bache hue akele comma/dash — "तेरह अप्रैल , बैसाखी" jaisa
    out = out.replace(" ,", ",").replace(" —,", " —").replace(",,", ",")
    return out.strip(" ,-—")


def hint_script(q: dict) -> str:
    """Jawab se PEHLE bola jaata hai — sirf wajah, naam nahi.

    Kyun: jawab sunte hi log swipe kar dete hain. Agar 'क्यों' jawab ke BAAD
    aaye to wo kabhi suna hi nahi jaata. Isliye pehle wajah, aur jawab
    video ki AAKHRI line."""
    why = (q.get("why") or "").strip()
    if not why:
        return "ध्यान से देखिए।"
    return f"एक इशारा — {mask_answer(why, q, 'ये')}"


def answer_script(q: dict) -> str:
    """Video ki aakhri line. Iske baad kuch nahi."""
    labels = ["ए", "बी", "सी", "डी"]
    return f"सही जवाब है — {labels[q['ans']]}, {q['opts'][q['ans']]}।"


def cta_script() -> str:
    """Timer ke turant baad, jawab se PEHLE.

    22-Sep-2026: subscribe/like engagement-bait bilkul hata diya.
    Sirf neutral transition: "अब सुनिए सही जवाब।"
    FAUJI_CTA ab bhi support hai agar kabhi wapas on karna ho.
    """
    if getattr(C, "FAUJI_CTA", False):
        # "जय हिंद" nahi bolna (Rajesh, 13-Sep-2026)
        return "अगर आप सच्चे देशभक्त हैं, तो वीडियो को लाइक और चैनल को सब्सक्राइब कीजिए। जवाब अभी बताती हूँ!"
    return "अब सुनिए सही जवाब।"


if __name__ == "__main__":
    p, d, e = say("नमस्ते, आज का सवाल।", "test")
    print(p, f"{d:.2f}s", e)
