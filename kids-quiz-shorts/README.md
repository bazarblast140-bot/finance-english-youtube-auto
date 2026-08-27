# Bacchon Ka GK — Hindi Quiz Shorts (Class 1-5)

> Ye `finance-english-youtube-auto` repo ke andar ek alag subfolder hai.
> Root ka finance long-form pipeline (`run_pipeline.py`) isse bilkul untouched hai.

Roz **5 YouTube Shorts** apne aap bante hain aur upload ho jaate hain
(4 quiz + 1 पहेली).
**Koi intro nahi.** Frame 0 se hi pehla sawaal dikhta hai aur bolna shuru
ho jaata hai — Shorts me viewer scroll karke aata hai, pehle 1-2 second me
sawaal shuru na ho to wo aage scroll kar deta hai. Branding sirf upar ke
banner me rehti hai.

Flow: सवाल बोला जाता है → 8s timer chalta hai (uske dauran A, B, C, D bole
jaate hain) → timer khatam → सही जवाब + "क्यों" → agla sawaal.

Har video me **2 sawaal** (do alag subject se), har sawaal pe **4 option**,
**8 second ka tik-tik timer**, phir **sahi jawab + ek line "क्यों"** — sirf ratna
nahi, samajhna. Voice **ElevenLabs female Hindi** hai; fail ho to apne aap
free `hi-IN-SwaraNeural` pe chali jaati hai.

**Paanch subject:** GK · Science · Maths · English · पहेली. Quiz slots
GK/Science/Maths/English rotate karte hain. **16:00 IST wala slot sirf
पहेली** hai — riddle search Hindi Shorts me strong hai.

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
| `ELEVENLABS_API_KEY` | Female Hindi voice — **`sk_` se shuru hona chahiye** |
| `ELEVENLABS_VOICE_ID` | ,, |

`ELEVENLABS_*` na daalo to script `hi-IN-SwaraNeural` (edge-tts, free) pe fall
back kar jaati hai — video phir bhi banega, bas voice alag hogi.

⚠️ **Sabse common galti:** ElevenLabs dashboard me jo value list me dikhti hai
wo key ka **ID** hai, asli API key nahi. Asli key **`sk_` se shuru** hoti hai
aur sirf banate/rotate karte waqt **ek baar** dikhti hai. ID daal doge to
`400 api_key_id_used_as_api_key` aayega aur voice chup-chaap free wali chalegi.
Script ab `sk_` check karke pehle hi warning de deti hai.

---

## Roz apne aap chalane ke liye

`.github/workflows/kids-gk-shorts.yml` already set hai:

| Slot | Cron (UTC) | IST | Kyun ye time |
|---|---|---|---|
| `morning` | `0 2 * * *`   | 07:30 | School jaane se pehle |
| `noon`    | `0 8 * * *`   | 13:30 | Lunch / ghar pe |
| `paheli`  | `30 10 * * *` | 16:00 | School ke baad — sirf पहेली |
| `evening` | `0 12 * * *`  | 17:30 | Homework se pehle |
| `night`   | `0 15 * * *`  | 20:30 | Khaane ke baad |

Naya slot jodna ho to **do jagah** badalna padega: workflow ka cron+case
block, aur `config.py` ka `SLOT_ORDER`.

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

`sub` ye ho sakte hain: `GK`, `Science`, `Maths`, `English`, `पहेली`.

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

**Bank:** 116 quiz sawaal ÷ **8 roz** (4 quiz video × 2) = **~14 din** quiz
cycle. **40 पहेली** ÷ 2 roz = **~20 din** paheli cycle. English/Maths
bottleneck pehle khatam honge (21-21).

⚠️ Quiz bank 14 din me repeat. Har subject ko 60 sawaal tak le jaana zaroori
hai. Paheli bank 40 se 80 tak badhana behtar hai.

**"सबसे" wale sawaal:** 25 superlative sawaal hain (`"topic": "सबसे"`) — duniya
ka sabse bada / ooncha / chhota / gehra / lamba. Ye sabse zyada search hone wale
kids GK sawaal hain, isliye inke liye SEO me alag tags bhi jud jaate hain.
Naya superlative daalo to `topic` field zaroor lagana.

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

**2c. Telegram notification.** Har run ke baad message aata hai — title,
duration, voice engine, subjects, aur YouTube link. Fail hone pe Actions log
ka link bhi. `TELEGRAM_BOT_TOKEN` aur `TELEGRAM_CHAT_ID` repo me pehle se hain.

Message me pinned comment ka text bhi aata hai — API se pin nahi hota (2b),
to phone se copy-paste karke chipka do.

Test karna ho bina bheje:
```bash
python src/notify.py --dir out/20260825_morning --slot morning \
  --privacy public --upload success --dry-run
```
Telegram fail ho to pipeline nahi rukti, par status `LAST_RUN.md` ke
`## telegram` section me poora dikh jaata hai (galat chat_id, bot blocked,
waghairah) — chup-chaap gayab nahi hota.

**3. YouTube quota.** Har upload ~1600 units. Daily quota 10,000 = ~6 upload/din.
5 video = ~8000 units — theek hai, par 6th extra run quota kha sakta hai.
Upload script me retry max 2 rakha hai taaki loop quota na kha jaye.

**4. ElevenLabs cost.** Har video me ~6 TTS call, roughly 400-500 characters.
5 video/din = ~75k characters/month. Apne plan ka limit dekh lena.
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
src/notify.py    Telegram notification (har run pe, pass ho ya fail)
```


---

## SEO — kya kaam karta hai, kya nahi

Ye 2026 ke Shorts behaviour pe based hai. Purana long-form SEO advice
(20 tags bharo, #shorts lagao) yahan ulta nuksan karta hai.

| Cheez | Hum kya karte hain | Kyun |
|---|---|---|
| Hashtag | **4** (broad → niche → subject → brand) | 15 se upar gaye to YouTube video ke **saare** hashtag ignore kar deta hai |
| `#shorts` | **nahi lagate** | YouTube ab ratio (9:16) + duration se Short pehchanta hai; har Short ye tag laga sakta hai isliye categorisation me kuch batata nahi |
| Tags | **8 specific** (pehle 21 the) | Tag volume nahi, relevance count hoti hai. Generic tag galat audience laata hai → low retention → algorithm neeche kar deta hai |
| Title | **sawaal sabse aage** | Mobile Shorts feed me title ki ek hi line dikhti hai (~45-55 char). Pehle "क्या तुम्हें पता है? 🤔" aage tha, jisse asli sawaal truncate ho jaata tha |
| Description | pehli line me keyword + sawaal | Pehle ~100 character sabse zyada weight rakhte hain |

**Sabse zaroori baat:** ye sab **chhota lever** hai. Shorts me discovery
mainly **retention aur swipe-away rate** se chalti hai. SEO sirf itna tay
karta hai ki video *kis* audience ko dikhaya jaaye — wo audience rukegi ya
nahi, wo video pe depend karta hai (hook, pacing, awaaz).

Yaani: title/tag se 200 views 400 nahi ho jaate. Pehle 2 second ka hook
aur timer ka pacing sudharo — asli growth wahan hai.
