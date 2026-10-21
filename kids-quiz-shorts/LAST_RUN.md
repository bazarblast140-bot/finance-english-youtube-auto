# Last run
- when   : 2026-10-21 10:15 UTC
- slot   : night
- privacy: public
- upload : success

## metadata
- title: दुनिया का सबसे ऊँचा जलप्रपात एंजेल फ़ॉल्स किस देश में है? 🤔 | World GK Quiz
- duration_sec: 20.37
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/35gpwig5qFI
- scheduled_for: 2026-10-21T15:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-21T15:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/35gpwig5qFI
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 95/344 fresh (~23.8 din)
[pick] stock paheli: 38/128 fresh (~38.0 din)
[pick] दुनिया/g262: दुनिया का सबसे ऊँचा जलप्रपात एंजेल फ़ॉल्स किस देश में है?
[hook] on-screen: आज का GK चैलेंज
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini key#1 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"473b1d8943108926104605e1b8a859eb"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
