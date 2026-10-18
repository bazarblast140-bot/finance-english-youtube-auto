# Last run
- when   : 2026-10-18 09:53 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: कौन सा रेलवे स्टेशन आधा महाराष्ट्र में और आधा गुजरात में है? 🤔 | India GK Quiz
- duration_sec: 19.5
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/r1Z2FIz0E1M
- scheduled_for: 2026-10-19T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-19T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/r1Z2FIz0E1M
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 107/344 fresh (~26.8 din)
[pick] stock paheli: 41/128 fresh (~41.0 din)
[pick] भारत/g301: कौन सा रेलवे स्टेशन आधा महाराष्ट्र में और आधा गुजरात में है?
[hook] on-screen: आज का GK चैलेंज
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"ded1792bee7c7652abb91996be1b3d72"}}
[tts] Gemini bad response (key#1): 'content'
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
