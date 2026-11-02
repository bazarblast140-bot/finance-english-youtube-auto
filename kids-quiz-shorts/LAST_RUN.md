# Last run
- when   : 2026-11-02 08:25 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: India GK Quiz in Hindi | भारत में सबसे पहले सूर्योदय किस राज्य में होत… 🤔 | India GK Question Answer
- duration_sec: 21.3
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/6xW-SegIcv8
- scheduled_for: 2026-11-03T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-03T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/6xW-SegIcv8
[thumb] set OK -> 6xW-SegIcv8
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 44/344 fresh (~11.0 din)
[pick] stock paheli: 25/128 fresh (~25.0 din)
[pick] भारत/g305: भारत में सबसे पहले सूर्योदय किस राज्य में होता है?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"8b06dccea5a31707f51ef514a5c7d22c"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
