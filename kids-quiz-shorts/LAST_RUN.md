# Last run
- when   : 2026-10-16 07:15 UTC
- slot   : night
- privacy: public
- upload : success

## metadata
- title: बांग्लादेश की मुद्रा का नाम क्या है? 🤔 | World GK Quiz
- duration_sec: 17.4
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/JblU4LXA5l4
- scheduled_for: 2026-10-16T15:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-16T15:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/JblU4LXA5l4
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 115/344 fresh (~28.8 din)
[pick] stock paheli: 43/128 fresh (~43.0 din)
[pick] दुनिया/g249: बांग्लादेश की मुद्रा का नाम क्या है?
[hook] on-screen: आज का GK चैलेंज
```

## voice
```
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini bad response (key#1): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"0d5e4856d813e4e318d10d57bb0ad817"}}
[tts] Gemini key#1 -> 429, agli key
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
