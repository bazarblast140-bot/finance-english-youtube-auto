# Last run
- when   : 2026-11-03 10:12 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: India GK Quiz in Hindi | भारत का राष्ट्रपति बनने के लिए न्यूनतम आयु कि… 🤔 | India GK Question Answer
- duration_sec: 21.27
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/xzeb_wNkOXY
- scheduled_for: 2026-11-04T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-04T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/xzeb_wNkOXY
[thumb] set OK -> xzeb_wNkOXY
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 40/344 fresh (~10.0 din)
[pick] stock paheli: 24/128 fresh (~24.0 din)
[pick] भारत/g205: भारत का राष्ट्रपति बनने के लिए न्यूनतम आयु कितनी है?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"a7c025f9938d6b18532ec6d1fcbc0505"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
