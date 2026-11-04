# Last run
- when   : 2026-11-04 08:11 UTC
- slot   : night
- privacy: public
- upload : success

## metadata
- title: World GK Quiz in Hindi | फ़्रांसीसी क्रांति किस साल शुरू हुई थी? 🤔 | World GK Question Answer
- duration_sec: 26.43
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/SG1Eeu_KuHE
- scheduled_for: 2026-11-04T15:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-04T15:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/SG1Eeu_KuHE
[thumb] set OK -> SG1Eeu_KuHE
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 39/344 fresh (~9.8 din)
[pick] stock paheli: 24/128 fresh (~24.0 din)
[pick] दुनिया/g254: फ़्रांसीसी क्रांति किस साल शुरू हुई थी?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini bad response (key#1): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"163eb80f4a68644e4550435b28454379"}}
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini key#1 -> 429, 30s cooldown, agli key/retry
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
