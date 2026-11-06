# Last run
- when   : 2026-11-06 11:09 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: India GK Quiz in Hindi | उल्कापिंड (meteorite) के टकराने से बनी लोनार… 🤔 | India GK Question Answer
- duration_sec: 23.0
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/SMy8zBQSPno
- scheduled_for: 2026-11-07T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-07T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/SMy8zBQSPno
[thumb] set OK -> SMy8zBQSPno
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 29/344 fresh (~7.2 din)
[pick] stock paheli: 21/128 fresh (~21.0 din)
[pick] भारत/g309: उल्कापिंड (meteorite) के टकराने से बनी लोनार झील किस राज्य में है?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"de31a6940fb0cc538e1e6d4a044be840"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
