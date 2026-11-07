# Last run
- when   : 2026-11-07 10:26 UTC
- slot   : paheli
- privacy: public
- upload : success

## metadata
- title: Hindi Paheli Quiz | किस सवाल का जवाब आप कभी 'हाँ' में नहीं दे सकते? 🤔 | Paheli with Answer
- duration_sec: 21.63
- voice_engines: ['gemini']
- youtube_url: https://youtube.com/shorts/SlJrdJHxhpw
- scheduled_for: 2026-11-08T10:30:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-08T10:30:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/SlJrdJHxhpw
[thumb] set OK -> SlJrdJHxhpw
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 24/344 fresh (~6.0 din) — WARNING: 7 din se kam. Naye sawaal data/questions.json me jodo; tab tak sabse purane sawaal (least-recently-used) dobara jaayenge.
[pick] stock paheli: 21/128 fresh (~21.0 din)
[pick] पहेली/ph119: किस सवाल का जवाब आप कभी 'हाँ' में नहीं दे सकते?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini key#2 -> 429, 11s cooldown, agli key/retry
[tts] Gemini: sab keys 429 — 11s ruk rahe hain
🎙  voice: gemini
```

## telegram
```
telegram: sent (http 200)
```
