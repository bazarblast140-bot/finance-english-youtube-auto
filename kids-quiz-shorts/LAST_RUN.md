# Last run
- when   : 2026-10-14 14:01 UTC
- slot   : noon
- privacy: public
- upload : success

## metadata
- title: कौन सा ग्रह सूरज के सबसे पास है? 🤔 | Science GK Quiz
- duration_sec: 18.27
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/CfhnxtwmIiQ
- scheduled_for: 2026-10-15T08:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-15T08:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/CfhnxtwmIiQ
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 123/344 fresh (~30.8 din)
[pick] stock paheli: 45/128 fresh (~45.0 din)
[pick] विज्ञान/g168: कौन सा ग्रह सूरज के सबसे पास है?
[hook] on-screen: ये आता है आपको?
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini key#1 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"9d8877440e86a66f1d282065956208fe"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
