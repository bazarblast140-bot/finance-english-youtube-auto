# Last run
- when   : 2026-11-11 08:30 UTC
- slot   : paheli
- privacy: public
- upload : success

## metadata
- title: Hindi Paheli Quiz | लंबे-लंबे कान, रुई जैसा बदन, गाजर खाए झटपट — वो कौन है? 🤔 | Paheli with Answer
- duration_sec: 23.07
- voice_engines: ['elevenlabs', 'gemini']
- youtube_url: https://youtube.com/shorts/JMlZOX7zFPg
- scheduled_for: 2026-11-12T10:30:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-12T10:30:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/JMlZOX7zFPg
[thumb] set OK -> JMlZOX7zFPg
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 8/344 fresh (~2.0 din) — WARNING: 7 din se kam. Naye sawaal data/questions.json me jodo; tab tak sabse purane sawaal (least-recently-used) dobara jaayenge.
[pick] stock paheli: 17/128 fresh (~17.0 din)
[pick] पहेली/ph98: लंबे-लंबे कान, रुई जैसा बदन, गाजर खाए झटपट — वो कौन है?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini key#2 -> 429, 42s cooldown, agli key/retry
[tts] Gemini: sab keys 429 — 42s ruk rahe hain
🎙  voice: elevenlabs, gemini
```

## telegram
```
telegram: sent (http 200)
```
