# Last run
- when   : 2026-10-15 10:00 UTC
- slot   : night
- privacy: public
- upload : success

## metadata
- title: किस बड़े देश में एक भी स्थायी नदी नहीं है? 🤔 | World GK Quiz
- duration_sec: 19.4
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/Pd9NbYwkIKk
- scheduled_for: 2026-10-15T15:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-15T15:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/Pd9NbYwkIKk
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 119/344 fresh (~29.8 din)
[pick] stock paheli: 44/128 fresh (~44.0 din)
[pick] दुनिया/g317: किस बड़े देश में एक भी स्थायी नदी नहीं है?
[hook] on-screen: ये आता है आपको?
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini key#1 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"c3e4230c56e24f25849307ff5dd17457"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
