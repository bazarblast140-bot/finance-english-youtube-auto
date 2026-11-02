# Last run
- when   : 2026-11-02 08:17 UTC
- slot   : morning
- privacy: public
- upload : success

## metadata
- title: GK Quiz in Hindi | भारत का 'मिसाइल मैन' किसे कहा जाता है? 🤔 | GK Question Answer
- duration_sec: 22.27
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/bTz_MupsoZE
- scheduled_for: 2026-11-03T02:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-03T02:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/bTz_MupsoZE
[thumb] set OK -> bTz_MupsoZE
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 46/344 fresh (~11.5 din)
[pick] stock paheli: 26/128 fresh (~26.0 din)
[pick] सामान्य ज्ञान/g275: भारत का 'मिसाइल मैन' किसे कहा जाता है?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini bad response (key#1): 'content'
[tts] Gemini bad response (key#1): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"eb6061b41ac6fe032ff46fde8bcdd920"}}
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
