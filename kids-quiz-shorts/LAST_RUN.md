# Last run
- when   : 2026-11-08 09:48 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: India GK Quiz in Hindi | भारतीय डाक का पिन कोड कुल कितने अंकों का होता… 🤔 | India GK Question Answer
- duration_sec: 21.77
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/RqRgwTkgkRU
- scheduled_for: 2026-11-09T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-09T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/RqRgwTkgkRU
[thumb] set OK -> RqRgwTkgkRU
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 20/344 fresh (~5.0 din) — WARNING: 7 din se kam. Naye sawaal data/questions.json me jodo; tab tak sabse purane sawaal (least-recently-used) dobara jaayenge.
[pick] stock paheli: 19/128 fresh (~19.0 din)
[pick] भारत/g307: भारतीय डाक का पिन कोड कुल कितने अंकों का होता है?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"e87206f79500e8ddea848b9b8beabd55"}}
[tts] Gemini key#2 -> 429 daily quota khatam, is run me band
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
