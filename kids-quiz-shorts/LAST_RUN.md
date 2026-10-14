# Last run
- when   : 2026-10-14 14:01 UTC
- slot   : paheli
- privacy: public
- upload : success

## metadata
- title: एक घर के दो दरवाज़े, दिन-रात आती-जाती हवा — वो क्या है? 🤔 | Hindi Paheli
- duration_sec: 22.17
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/3DN-C6iAoKI
- scheduled_for: 2026-10-15T10:30:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-15T10:30:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/3DN-C6iAoKI
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 123/344 fresh (~30.8 din)
[pick] stock paheli: 45/128 fresh (~45.0 din)
[pick] पहेली/ph106: एक घर के दो दरवाज़े, दिन-रात आती-जाती हवा — वो क्या है?
[hook] on-screen: आज की पहेली
```

## voice
```
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini bad response (key#1): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"1454b9d9827e6057fee93af8e072a2e1"}}
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini key#2 -> 429, agli key
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
