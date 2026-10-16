# Last run
- when   : 2026-10-16 07:15 UTC
- slot   : paheli
- privacy: public
- upload : success

## metadata
- title: एक फल ऐसा, जिसका बीज बाहर लटका रहता है — इनमें से कौन? 🤔 | Hindi Paheli
- duration_sec: 25.67
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/JL5XJTIkWMA
- scheduled_for: 2026-10-17T10:30:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-17T10:30:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/JL5XJTIkWMA
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 115/344 fresh (~28.8 din)
[pick] stock paheli: 43/128 fresh (~43.0 din)
[pick] पहेली/ph115: एक फल ऐसा, जिसका बीज बाहर लटका रहता है — इनमें से कौन?
[hook] on-screen: दिमाग़ लगाइए!
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini key#1 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"1ecbf5ab0a073de34a23feb90203fc41"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
