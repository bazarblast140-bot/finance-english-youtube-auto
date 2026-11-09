# Last run
- when   : 2026-11-09 12:14 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: India GK Quiz in Hindi | 'भारत का स्कॉटलैंड' कहलाने वाला कूर्ग (कोडगु)… 🤔 | India GK Question Answer
- duration_sec: 20.13
- voice_engines: ['elevenlabs', 'gemini']
- youtube_url: https://youtube.com/shorts/ZjLZ69NAbgk
- scheduled_for: 2026-11-10T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-10T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/ZjLZ69NAbgk
[thumb] set OK -> ZjLZ69NAbgk
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 16/344 fresh (~4.0 din) — WARNING: 7 din se kam. Naye sawaal data/questions.json me jodo; tab tak sabse purane sawaal (least-recently-used) dobara jaayenge.
[pick] stock paheli: 18/128 fresh (~18.0 din)
[pick] भारत/g312: 'भारत का स्कॉटलैंड' कहलाने वाला कूर्ग (कोडगु) किस राज्य में है?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini key#2 -> 429 daily quota khatam, is run me band
🎙  voice: elevenlabs, gemini
```

## telegram
```
telegram: sent (http 200)
```
