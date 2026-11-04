# Last run
- when   : 2026-11-04 08:19 UTC
- slot   : paheli
- privacy: public
- upload : success

## metadata
- title: Hindi Paheli Quiz | ख़ुद गीला होकर दूसरों को सुखाए — वो क्या है? 🤔 | Paheli with Answer
- duration_sec: 23.0
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/os1Kv8jMBbA
- scheduled_for: 2026-11-05T10:30:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-05T10:30:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/os1Kv8jMBbA
[thumb] set OK -> os1Kv8jMBbA
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 36/344 fresh (~9.0 din)
[pick] stock paheli: 24/128 fresh (~24.0 din)
[pick] पहेली/ph80: ख़ुद गीला होकर दूसरों को सुखाए — वो क्या है?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini key#2 -> 429 daily quota khatam, is run me band
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"c0b22a6f9a98b0db9de61980bb866041"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
