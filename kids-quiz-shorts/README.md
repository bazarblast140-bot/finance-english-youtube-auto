# Bacchon Ka GK — Hindi Quiz Shorts (Class 1-5)

> Ye `finance-english-youtube-auto` repo ke andar ek alag subfolder hai.
> Root ka finance long-form pipeline (`run_pipeline.py`) isse bilkul untouched hai.

Roz **subah aur shaam** ek-ek YouTube Short apne aap banta hai aur upload ho jaata hai.
Har video me **2 sawaal** (do alag subject se), har sawaal pe **4 option**,
**8 second ka tik-tik timer**, phir **sahi jawab + ek line "क्यों"** — sirf ratna
nahi, samajhna. Voice **ElevenLabs female Hindi** hai; fail ho to apne aap
free `hi-IN-SwaraNeural` pe chali jaati hai.

**Chaar subject:** GK · Science · Maths · English. Har din slot ke hisaab se
rotate hote hain, taaki hafte bhar me chaaron barabar aayein.

Video: 1080x1920, 30fps, ~52-60 second.

**Length ke baare me:** Shorts ki asli limit **3 minute** hai (Oct 2024 se;
pehle 60s thi). Hum 60s ke aas-paas isliye rehte hain kyunki engagement ka
sweet spot 30-60s hai — ye retention ka target hai, platform ka rule nahi.
`config.py` me `TARGET_SECONDS` aur `HARD_LIMIT_SECONDS` alag-alag hain.

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

### YouTube auth (ek baar, laptop pe — CI me nahi hoga)

1. Google Cloud Console → naya project → **YouTube Data API v3** enable karo
2. OAuth client banao, type **Desktop app** → `client_secret.json` download
3. `python src/upload.py --auth` chalao, browser me channel se login karo
4. Terminal pe jo 3 values print hongi, unhe GitHub repo → Settings → Secrets me daalo:
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`

Secrets me ye naam use karo (finance channel wale `YOUTUBE_*` se alag rakhna
zaroori hai):

| Secret | Kyun |
|---|---|
| `KIDS_YT_CLIENT_ID` | Kids channel ka OAuth client |
| `KIDS_YT_CLIENT_SECRET` | ,, |
| `KIDS_YT_REFRESH_TOKEN` | Kids channel se login karke banaya |
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
{"id": "sc23", "sub": "Science", "q": "सवाल?",
 "opts": ["A","B","C","D"], "ans": 2,
 "why": "एक line me reason — ye reveal screen pe dikhta hai aur bola bhi jaata hai."}
```

`sub` sirf ye chaar ho sakte hain: `GK`, `Science`, `Maths`, `English`.

### Option ke aage icon

`data/icons.json` me option text -> emoji ka map hai. Rule **all-or-nothing**
hai: sawaal ke **chaaron** option ka icon map me mile tabhi icons dikhte hain,
warna sirf text. Aadha-adhura icon set bhadda lagta hai.

Isi wajah se Maths (गिनती) aur English grammar wale sawaal apne aap icon se
bahar reh jaate hain — wahan icon ka koi matlab bhi nahi. Abhi **38/91** sawaal
ko icon milta hai.

Naya icon jodna ho to bas map me line add kar do — sawaal chhune ki zaroorat
nahi, wo apne aap utha lega:

```json
"शुतुरमुर्ग": "🦤"
```

CI pe `fonts-noto-color-emoji` chahiye (workflow me already hai). Wo na ho to
icons chup-chaap gayab ho jaate hain, isliye workflow me ek warning check bhi
lagaya hai.
`why` mandatory hai — chhota rakho (60-70 char), warna video 60s cross kar jaayega.

`ans` = 0-based index. `data/used.json` khud maintain hoti hai — wahi sawaal
dobara nahi aayega jab tak poora bank khatam na ho jaye.

**Bank abhi chhota hai:** 91 sawaal ÷ 4 roz = **~22 din**. Uske baad cycle reset
hoke purane sawaal repeat honge. English aur Maths sabse pehle khatam honge
(21-21 hain). Teen hafte ke andar har subject ko 60+ tak le jaao.

---

## Dhyan dene wali cheezein

**1. Made for Kids = False set hai.** Comments chaalu rahein aur personalized
ads se RPM bacha rahe, isliye. Matlab tum YouTube ko keh rahe ho ki video
bacchon ke liye "directed" nahi hai — audience parents/teachers hain. Content
khud class 1-5 syllabus ka hai, to ye grey area hai; compliance call tumhara
hai. **Channel Settings → Audience me bhi "No, it's not made for kids" hi
rakhna** — warna channel-level setting video-level ko override kar degi aur
comments phir bhi band ho jaayenge.

**1b. Wrong-channel guard.** Is repo ke `YOUTUBE_*` secrets *The Money Rule*
(finance English) channel ke hain. Kids short unse upload hua to galat channel
pe chala jaayega. Isliye workflow sirf `KIDS_YT_CLIENT_ID` /
`KIDS_YT_CLIENT_SECRET` / `KIDS_YT_REFRESH_TOKEN` use karta hai. Ye set nahi
honge to upload skip ho jaata hai aur video Actions artifact me milta hai —
kuch galat jagah nahi jaayega.

**2. Voice fallback.** Order: ElevenLabs → `hi-IN-SwaraNeural` (edge-tts, free)
→ silent. ElevenLabs ka quota/key fail ho to build rukta nahi, apne aap free
voice pe chal jaata hai — log me `voice: edge` dikhega aur build ke ant me
saaf likha aata hai ki ElevenLabs fail hua. Sirf teeno fail hone pe silent
video banta hai, aur us case me workflow ka volume-check upload rok deta hai.

**2b. Pinned comment API se nahi lagta.** `metadata.json` me `pinned_comment`
ready hota hai, par usse post karne ke liye jo scope chahiye wo tumhare
refresh token me granted nahi hai (403 aata hai, aur script use chup-chaap
skip kar deti hai). Comment khud paste kar do, ya `youtube_auth.py` dobara
chala ke naya token banao.

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
