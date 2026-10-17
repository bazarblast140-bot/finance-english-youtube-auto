# Last run
- when   : 2026-10-17 09:26 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: दुनिया का सबसे ऊँचा रेलवे आर्च पुल 'चिनाब ब्रिज' कहाँ है? 🤔 | India GK Quiz
- duration_sec: 19.83
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/E7e1BkX6gnI
- scheduled_for: 2026-10-18T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-18T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/E7e1BkX6gnI
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 111/344 fresh (~27.8 din)
[pick] stock paheli: 42/128 fresh (~42.0 din)
[pick] भारत/g302: दुनिया का सबसे ऊँचा रेलवे आर्च पुल 'चिनाब ब्रिज' कहाँ है?
[hook] on-screen: पक्का पता है?
```

## voice
```
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini key#1 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"162499f3774c2e896d8566254520831f"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
