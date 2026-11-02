# Last run
- when   : 2026-11-02 08:22 UTC
- slot   : paheli
- privacy: public
- upload : success

## metadata
- title: Hindi Paheli Quiz | आता है पर कभी जाता नहीं — वो क्या है? 🤔 | Paheli with Answer
- duration_sec: 22.17
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/jIL-WHRgEMo
- scheduled_for: 2026-11-03T10:30:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-03T10:30:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/jIL-WHRgEMo
[thumb] set OK -> jIL-WHRgEMo
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 44/344 fresh (~11.0 din)
[pick] stock paheli: 26/128 fresh (~26.0 din)
[pick] पहेली/ph91: आता है पर कभी जाता नहीं — वो क्या है?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"75c836b0c42cf5c7951da1df133bb880"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
