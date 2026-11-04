# Last run
- when   : 2026-11-04 08:22 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: India GK Quiz in Hindi | भारत छोड़ो आंदोलन किस साल शुरू हुआ था? 🤔 | India GK Question Answer
- duration_sec: 31.0
- voice_engines: ['edge']
- youtube_url: https://youtube.com/shorts/uEP9czmFyrc
- scheduled_for: 2026-11-05T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-05T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/uEP9czmFyrc
[thumb] set OK -> uEP9czmFyrc
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 36/344 fresh (~9.0 din)
[pick] stock paheli: 23/128 fresh (~23.0 din)
[pick] भारत/g208: भारत छोड़ो आंदोलन किस साल शुरू हुआ था?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini key#2 -> 429 daily quota khatam, is run me band
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"a5cfe09e3441f6cb453b468e6d79db08"}}
🎙  voice: edge  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
