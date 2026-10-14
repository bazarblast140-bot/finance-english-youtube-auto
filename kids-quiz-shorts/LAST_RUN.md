# Last run
- when   : 2026-10-14 14:01 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: कौन सा भारतीय राज्य तीन तरफ़ से बांग्लादेश से घिरा है? 🤔 | India GK Quiz
- duration_sec: 23.47
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/zED-fIUHMi0
- scheduled_for: 2026-10-15T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-15T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/zED-fIUHMi0
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 123/344 fresh (~30.8 din)
[pick] stock paheli: 45/128 fresh (~45.0 din)
[pick] भारत/g214: कौन सा भारतीय राज्य तीन तरफ़ से बांग्लादेश से घिरा है?
[hook] on-screen: पक्का पता है?
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini key#1 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"b0230796d235f0c03b72fa0a975a433b"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
