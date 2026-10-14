# Last run
- when   : 2026-10-14 14:01 UTC
- slot   : night
- privacy: public
- upload : success

## metadata
- title: गर्मियों में पेरिस का एफ़िल टॉवर धातु फैलने से लगभग कितना ऊँचा हो जाता है? 🤔 | World GK Quiz
- duration_sec: 24.43
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/KIwwh5LSHxI
- scheduled_for: 2026-10-14T15:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-14T15:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/KIwwh5LSHxI
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 123/344 fresh (~30.8 din)
[pick] stock paheli: 45/128 fresh (~45.0 din)
[pick] दुनिया/g328: गर्मियों में पेरिस का एफ़िल टॉवर धातु फैलने से लगभग कितना ऊँचा हो जाता है?
[hook] on-screen: सोचिए, फिर बताइए!
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"3350f9db7e2b228bc14f2632b50f3e15"}}
[tts] Gemini key#1 -> 429, agli key
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
