# Last run
- when   : 2026-10-15 10:00 UTC
- slot   : noon
- privacy: public
- upload : success

## metadata
- title: कौन सा ग्रह इतना कम घना है कि पानी में तैर सकता है? 🤔 | Science GK Quiz
- duration_sec: 19.8
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/LUvF9l42-DU
- scheduled_for: 2026-10-16T08:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-16T08:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/LUvF9l42-DU
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 119/344 fresh (~29.8 din)
[pick] stock paheli: 44/128 fresh (~44.0 din)
[pick] विज्ञान/g293: कौन सा ग्रह इतना कम घना है कि पानी में तैर सकता है?
[hook] on-screen: सोचिए, फिर बताइए!
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini key#1 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"57985a2273a8be313707a18a0895b56d"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
