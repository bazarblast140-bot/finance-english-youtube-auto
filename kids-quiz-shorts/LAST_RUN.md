# Last run
- when   : 2026-11-05 11:53 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: India GK Quiz in Hindi | 'एशिया का सबसे साफ़ गाँव' कहलाने वाला मावलिनन… 🤔 | India GK Question Answer
- duration_sec: 22.6
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/ZOcSBguZMI0
- scheduled_for: 2026-11-06T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-06T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/ZOcSBguZMI0
[thumb] set OK -> ZOcSBguZMI0
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 32/344 fresh (~8.0 din)
[pick] stock paheli: 22/128 fresh (~22.0 din)
[pick] भारत/g300: 'एशिया का सबसे साफ़ गाँव' कहलाने वाला मावलिननॉन्ग किस राज्य में है?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini key#2 -> 429 daily quota khatam, is run me band
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"85342fe1d509c8253f74cdbd213d272c"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
