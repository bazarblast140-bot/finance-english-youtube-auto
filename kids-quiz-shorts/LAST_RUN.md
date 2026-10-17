# Last run
- when   : 2026-10-17 09:26 UTC
- slot   : paheli
- privacy: public
- upload : success

## metadata
- title: वो कौन सा शब्द है जो हर शब्दकोश में 'ग़लत' ही लिखा होता है? 🤔 | Hindi Paheli
- duration_sec: 21.47
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/nvzRf40AokI
- scheduled_for: 2026-10-18T10:30:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-18T10:30:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/nvzRf40AokI
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 111/344 fresh (~27.8 din)
[pick] stock paheli: 42/128 fresh (~42.0 din)
[pick] पहेली/ph82: वो कौन सा शब्द है जो हर शब्दकोश में 'ग़लत' ही लिखा होता है?
[hook] on-screen: बूझिए तो जानें!
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini key#1 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"c7056c5091b2c8d98c3a7ef2324d23c9"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
