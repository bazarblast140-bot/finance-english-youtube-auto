# Last run
- when   : 2026-10-29 08:45 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: मोर को भारत का राष्ट्रीय पक्षी किस वर्ष घोषित किया गया? 🤔 | India GK Quiz
- duration_sec: 24.87
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/7JPInbkQLOs
- scheduled_for: 2026-10-30T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-30T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/7JPInbkQLOs
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 60/344 fresh (~15.0 din)
[pick] stock paheli: 29/128 fresh (~29.0 din)
[pick] भारत/g171: मोर को भारत का राष्ट्रीय पक्षी किस वर्ष घोषित किया गया?
[hook] on-screen: आज का GK चैलेंज
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"bac241c9b12ed7153143d61a8c83c213"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
