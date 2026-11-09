# Last run
- when   : 2026-11-09 12:10 UTC
- slot   : noon
- privacy: public
- upload : success

## metadata
- title: Science GK Quiz in Hindi | सौरमंडल का सबसे बड़ा ग्रह कौन सा है? 🤔 | Science GK Question Answer
- duration_sec: 18.53
- voice_engines: ['elevenlabs', 'gemini']
- youtube_url: https://youtube.com/shorts/vy8cMsxXVic
- scheduled_for: 2026-11-10T08:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-10T08:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/vy8cMsxXVic
[thumb] set OK -> vy8cMsxXVic
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 17/344 fresh (~4.2 din) — WARNING: 7 din se kam. Naye sawaal data/questions.json me jodo; tab tak sabse purane sawaal (least-recently-used) dobara jaayenge.
[pick] stock paheli: 19/128 fresh (~19.0 din)
[pick] विज्ञान/g162: सौरमंडल का सबसे बड़ा ग्रह कौन सा है?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini key#2 -> 429, 57s cooldown, agli key/retry
[tts] Gemini: sab keys 429 — 57s ruk rahe hain
🎙  voice: elevenlabs, gemini
```

## telegram
```
telegram: sent (http 200)
```
