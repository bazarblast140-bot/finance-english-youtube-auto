# Last run
- when   : 2026-10-19 07:09 UTC
- slot   : paheli
- privacy: public
- upload : success

## metadata
- title: आती है तो सब सो जाते हैं, जाती है तो सब जाग जाते हैं — वो क्या है? 🤔 | Hindi Paheli
- duration_sec: 22.03
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/QV83FZCLWPY
- scheduled_for: 2026-10-20T10:30:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-20T10:30:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/QV83FZCLWPY
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 103/344 fresh (~25.8 din)
[pick] stock paheli: 40/128 fresh (~40.0 din)
[pick] पहेली/ph113: आती है तो सब सो जाते हैं, जाती है तो सब जाग जाते हैं — वो क्या है?
[hook] on-screen: 8 सेकंड में बूझिए!
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini key#1 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"6ef7241bf0049f78d2f4aebe0c4e2e72"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
