# Last run
- when   : 2026-10-18 09:53 UTC
- slot   : paheli
- privacy: public
- upload : success

## metadata
- title: एक पक्षी ऐसा, जिसकी दुम पर पैसा; बादल देख नाचे — वो कौन है? 🤔 | Hindi Paheli
- duration_sec: 22.87
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/cKoq8zKaGf0
- scheduled_for: 2026-10-19T10:30:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-19T10:30:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/cKoq8zKaGf0
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 107/344 fresh (~26.8 din)
[pick] stock paheli: 41/128 fresh (~41.0 din)
[pick] पहेली/ph103: एक पक्षी ऐसा, जिसकी दुम पर पैसा; बादल देख नाचे — वो कौन है?
[hook] on-screen: दिमाग़ लगाइए!
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini key#1 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"33a3a3aed2de260dd764495f4b21d589"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
