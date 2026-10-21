# Last run
- when   : 2026-10-21 10:15 UTC
- slot   : noon
- privacy: public
- upload : success

## metadata
- title: सबसे हल्की गैस कौन सी है? 🤔 | Science GK Quiz
- duration_sec: 19.1
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/sUGJjTXHMeQ
- scheduled_for: 2026-10-22T08:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-22T08:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/sUGJjTXHMeQ
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 95/344 fresh (~23.8 din)
[pick] stock paheli: 38/128 fresh (~38.0 din)
[pick] विज्ञान/g234: सबसे हल्की गैस कौन सी है?
[hook] on-screen: 8 सेकंड में जवाब दीजिए!
```

## voice
```
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini key#2 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"68c485cf121337472df8782650ec47b9"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
