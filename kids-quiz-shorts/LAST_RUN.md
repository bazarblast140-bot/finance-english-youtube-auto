# Last run
- when   : 2026-10-16 07:15 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: भारत का तैरता हुआ डाकघर (floating post office) कहाँ है? 🤔 | India GK Quiz
- duration_sec: 30.5
- voice_engines: ['edge']
- youtube_url: https://youtube.com/shorts/DTCWWhTgjYc
- scheduled_for: 2026-10-17T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-17T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/DTCWWhTgjYc
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 115/344 fresh (~28.8 din)
[pick] stock paheli: 43/128 fresh (~43.0 din)
[pick] भारत/g308: भारत का तैरता हुआ डाकघर (floating post office) कहाँ है?
[hook] on-screen: पक्का पता है?
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini key#2 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"ce63e77c6266d28048808e0009b7f8b2"}}
🎙  voice: edge  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
