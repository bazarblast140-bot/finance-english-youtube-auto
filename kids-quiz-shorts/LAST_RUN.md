# Last run
- when   : 2026-10-20 10:30 UTC
- slot   : paheli
- privacy: public
- upload : success

## metadata
- title: काली है पर कौआ नहीं, लंबी है पर डंडा नहीं, रोज़ बाँधी जाती है — वो क्या है? 🤔 | Hindi Paheli
- duration_sec: 21.77
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/Ap-M831wDVU
- scheduled_for: 2026-10-21T10:30:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-21T10:30:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/Ap-M831wDVU
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 99/344 fresh (~24.8 din)
[pick] stock paheli: 39/128 fresh (~39.0 din)
[pick] पहेली/ph87: काली है पर कौआ नहीं, लंबी है पर डंडा नहीं, रोज़ बाँधी जाती है — वो क्या है?
[hook] on-screen: दिमाग़ लगाइए!
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini key#2 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"8abc4f145e4004624c2a0647e3f65642"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
