# Last run
- when   : 2026-11-04 08:16 UTC
- slot   : noon
- privacy: public
- upload : success

## metadata
- title: Science GK Quiz in Hindi | जिराफ़ की लंबी गर्दन में कितनी हड्डियाँ (… 🤔 | Science GK Question Answer
- duration_sec: 25.27
- voice_engines: ['edge', 'gemini']
- youtube_url: https://youtube.com/shorts/-2UlSHKm9oY
- scheduled_for: 2026-11-05T08:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-05T08:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/-2UlSHKm9oY
[thumb] set OK -> -2UlSHKm9oY
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 37/344 fresh (~9.2 din)
[pick] stock paheli: 24/128 fresh (~24.0 din)
[pick] विज्ञान/g298: जिराफ़ की लंबी गर्दन में कितनी हड्डियाँ (कशेरुकाएँ) होती हैं?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] ElevenLabs FAIL 401: {"detail":{"type":"payment_required","code":"payment_issue","message":"Your subscription has a failed or incomplete payment. Complete the latest invoice to continue usage.","status":"payment_issue","request_id":"2068fd8f641fd555084f5e9794563c1e"}}
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
🎙  voice: edge, gemini  <- ElevenLabs fail hua, free voice pe chala
```

## telegram
```
telegram: sent (http 200)
```
