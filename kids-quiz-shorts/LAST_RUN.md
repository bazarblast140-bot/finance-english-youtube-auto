# Last run
- when   : 2026-11-07 10:28 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: India GK Quiz in Hindi | पानीपत का पहला युद्ध (1526) किनके बीच हुआ था? 🤔 | India GK Question Answer
- duration_sec: 25.9
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/aIg71DgAMTA
- scheduled_for: 2026-11-08T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-08T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/aIg71DgAMTA
[thumb] set OK -> aIg71DgAMTA
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 24/344 fresh (~6.0 din) — WARNING: 7 din se kam. Naye sawaal data/questions.json me jodo; tab tak sabse purane sawaal (least-recently-used) dobara jaayenge.
[pick] stock paheli: 20/128 fresh (~20.0 din)
[pick] भारत/g206: पानीपत का पहला युद्ध (1526) किनके बीच हुआ था?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini key#2 -> 429 daily quota khatam, is run me band
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"1bbd5e178de8513c0666a95294393be5"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
