# Last run
- when   : 2026-11-04 08:14 UTC
- slot   : morning
- privacy: public
- upload : success

## metadata
- title: GK Quiz in Hindi | 'सोमवार' का नाम किस पर रखा गया है? 🤔 | GK Question Answer
- duration_sec: 20.07
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/N_hQ9Yc48tc
- scheduled_for: 2026-11-05T02:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-05T02:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/N_hQ9Yc48tc
[thumb] set OK -> N_hQ9Yc48tc
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 38/344 fresh (~9.5 din)
[pick] stock paheli: 24/128 fresh (~24.0 din)
[pick] सामान्य ज्ञान/g333: 'सोमवार' का नाम किस पर रखा गया है?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini bad response (key#1): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"f0095ffe53c7b4348fb330f65bde76c7"}}
[tts] Gemini key#1 -> 429, 17s cooldown, agli key/retry
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
