# Last run
- when   : 2026-10-21 10:15 UTC
- slot   : morning
- privacy: public
- upload : success

## metadata
- title: ज़्यादातर चमगादड़ अंधेरे में रास्ता कैसे खोजते हैं? 🤔 | GK Quiz Hindi
- duration_sec: 22.1
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/AUK01lLqUww
- scheduled_for: 2026-10-22T02:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-10-22T02:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/AUK01lLqUww
[upload] comment abhi nahi gaya (baad me retry): <HttpError 403 when requesting https://youtube.googleapis.com/youtube/v3/commentThreads?part=snippet&alt=json returned "The comment thread could not be created due to insufficient permissions. The request might not be properly authorized.". Details: "[{'message': 'The comment thread could not be cre
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 95/344 fresh (~23.8 din)
[pick] stock paheli: 38/128 fresh (~38.0 din)
[pick] सामान्य ज्ञान/g280: ज़्यादातर चमगादड़ अंधेरे में रास्ता कैसे खोजते हैं?
[hook] on-screen: पक्का पता है?
```

## voice
```
[tts] Gemini key#1 -> 429, agli key
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini key#1 -> 429, agli key
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"4124f2af75689ee5db94cd9c42da3f3f"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
