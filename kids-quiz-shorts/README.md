# QUIZ PATHSHALA — Hindi Quiz Shorts (Class 1-5)

> Ye `finance-english-youtube-auto` repo ke andar ek alag subfolder hai.
> Root ka finance long-form pipeline (`run_pipeline.py`) isse bilkul untouched hai.

Channel: **QUIZ PATHSHALA** (@QuizPathshalaIndia). Roz **subah aur shaam** ek-ek YouTube Short apne aap banta hai aur upload ho jaata hai.
Har video me **2 sawaal**, har sawaal pe **4 option**, **8 second ka tik-tik timer**,
phir **sahi jawab reveal** — aur voice **ElevenLabs ki female Hindi** hai.

Video: 1080x1920, 30fps, ~45-52 second (Shorts shelf ki 60s limit ke andar).

---

## Setup (ek baar)

```bash
# 1. deps
sudo apt-get install -y ffmpeg fonts-noto-core fonts-indic libraqm0
pip install -r requirements.txt

# 2. env
cp .env.example .env      # apni keys bharo
set -a; source .env; set +a

# 3. test video (upload nahi hoga, sawaal history me bhi nahi jayega)
python src/build.py --slot morning --dry-run
```

Output `out/YYYYMMDD_morning/` me milega — MP4 + `metadata.json`.

### YouTube auth

Already done — repo ke `YOUTUBE_*` secrets isi channel ke hain. Sirf tab
dobara banana padega agar tum naya alag channel kholo:
`python src/upload.py --auth` (laptop pe, CI me interactive login nahi hota).

YouTube ke `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` /
`YOUTUBE_REFRESH_TOKEN` secrets is repo me **pehle se set hain** — kuch
karne ki zaroorat nahi. Sirf ye do naye daalne hain:

| Secret | Kyun |
|---|---|
| `ELEVENLABS_API_KEY` | Female Hindi voice |
| `ELEVENLABS_VOICE_ID` | ,, |

`ELEVENLABS_*` na daalo to script `hi-IN-SwaraNeural` (edge-tts, free) pe fall
back kar jaati hai — video phir bhi banega, bas voice alag hogi.

---

## Roz apne aap chalane ke liye

`.github/workflows/kids-gk-shorts.yml` already set hai:

| Slot  | Cron (UTC)   | IST       |
|-------|--------------|-----------|
| Subah | `0 2 * * *`  | 07:30 AM  |
| Shaam | `0 13 * * *` | 06:30 PM  |

Manual chalane ke liye: Actions tab → *Kids GK Quiz Shorts* → **Run workflow**
(default privacy `unlisted` hai — pehla run dekh lo, phir `public` karna).

**GitHub cron on-time nahi hai** — peak load pe 5-30 min late chal sakta hai.
Agar exact time chahiye to workflow me `--publish-at '2026-08-26T02:00:00Z'`
add kar do: video pehle private upload hoga, YouTube khud exact second pe public karega.

---

## Kya kahan badalna hai

Sab kuch `src/config.py` me hai:

| Chahiye | Badlo |
|---|---|
| 8 second ki jagah 10 | `TIMER_SECONDS` |
| 2 ki jagah 3 sawaal | `QUESTIONS_PER_VIDEO` (dhyan: 60s limit) |
| Rang / brand naam | `COLORS`, `BRAND`, `HANDLE` |
| Voice ki speed/tone | `ELEVEN_STABILITY`, `ELEVEN_SPEED` |
| Tik-tik loud/halka | `TICK_VOLUME` |

**Naye sawaal** `data/questions.json` me add karo:

```json
{"id": "ani16", "cat": "जानवर", "q": "सवाल?", "opts": ["A","B","C","D"], "ans": 2}
```

`ans` = 0-based index. `data/used.json` khud maintain hoti hai — wahi sawaal
dobara nahi aayega jab tak poora bank khatam na ho jaye.

**Bank abhi chhota hai:** 70 sawaal ÷ 4 sawaal roz (2 per video × 2 video) =
**sirf 17 din**. Uske baad cycle reset hoke purane sawaal repeat hone lagenge.
Do hafte ke andar bank ko 200+ tak le jaao, warna audience ko repeat dikhega.

---

## Dhyan dene wali cheezein

**1. Made for Kids = False set hai.** Comments chaalu rahein aur personalized
ads se RPM bacha rahe, isliye. Matlab tum YouTube ko keh rahe ho ki video
bacchon ke liye "directed" nahi hai — audience parents/teachers hain. Content
khud class 1-5 syllabus ka hai, to ye grey area hai; compliance call tumhara
hai. **Channel Settings → Audience me bhi "No, it's not made for kids" hi
rakhna** — warna channel-level setting video-level ko override kar degi aur
comments phir bhi band ho jaayenge.

**1b. Channel.** Wahi channel jo pehle *The Money Rule* tha — rename karke kids
GK bana diya gaya hai. Isliye repo ke maujuda `YOUTUBE_CLIENT_ID` /
`YOUTUBE_CLIENT_SECRET` / `YOUTUBE_REFRESH_TOKEN` secrets hi use ho rahe hain,
kuch naya nahi banana.

**1c. Purane finance videos.** Channel ka naam badal gaya, par purane English
finance videos wahin hain. YouTube ka algorithm mixed signal padhta hai
(English finance viewers ko Hindi kids GK recommend karega — dono fail).
Purane videos ko **private** kar do (delete mat karna — analytics chali
jaayegi). `daily-finance.yml` ka cron already paused hai, to naye finance
videos ab nahi banenge.

**2. Voice fail ho to upload nahi hoga.** Workflow me ek check hai jo video ka
mean volume dekhta hai. ElevenLabs quota khatam ho jaye to script silent
fallback pe chali jaati hai — us silent video ko check pakad ke upload rok deta hai.
Log me `SILENT fallback used` dikhega.

**3. YouTube quota.** Har upload ~1600 units. Daily quota 10,000 = ~6 upload/din.
Tumhein 2 chahiye, so theek hai — par upload script me retry max 2 rakha hai
taaki koi loop ek din ka quota na kha jaye.

**4. ElevenLabs cost.** Har video me 6 TTS call jaati hai (intro + 2 sawaal +
2 jawab + outro), roughly 400-500 characters. 2 video/din = ~30k characters/month.
Apne plan ka character limit dekh lena — Starter plan pe ye fit ho jaayega.
Voice cache bhi hai (`out/voice_cache/`), so same text dobara paisa nahi legega.

**5. ElevenLabs API shape.** `src/tts.py` ka request format apne current docs se
ek baar match kar lena — main isse live verify nahi kar paaya. Agar 4xx aaye to
error text log me poora print hota hai.

---

## Files

```
src/config.py    saare settings — sirf yahin badlo
src/pick.py      sawaal chunna + repeat rokna
src/tts.py       ElevenLabs -> edge-tts -> silent fallback
src/sfx.py       tik-tik, ding, whoosh — code se bante hain (no copyright)
src/render.py    1080x1920 frames
src/build.py     sab jodta hai -> MP4 + metadata.json
src/seo.py       title, description, tags, hashtags
src/upload.py    YouTube Data API v3
```
