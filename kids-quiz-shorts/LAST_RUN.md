# Last run
- when   : 2026-11-20 09:28 UTC
- slot   : evening
- privacy: public
- upload : success

## metadata
- title: India GK Quiz in Hindi | संविधान सभा ने भारतीय संविधान किस दिन अंगीकृत… 🤔 | India GK Question Answer
- duration_sec: 28.6
- voice_engines: ['elevenlabs', 'gemini']
- youtube_url: https://youtube.com/shorts/BZqDf-BKus8
- scheduled_for: 2026-11-21T12:00:00Z

## upload output (tail)
```
[upload] privacy=private + publishAt=2026-11-21T12:00:00Z
[upload] token scopes: youtube, youtube.force-ssl, youtube.readonly, youtube.upload
[upload] channel: QUIZ PATHSHALA
[upload] done -> https://youtube.com/shorts/BZqDf-BKus8
[thumb] set OK -> BZqDf-BKus8
[upload] comment abhi skip: video private/scheduled hai (YouTube 403 deta). Public hone ke baad catch-up pending comment daalega.
```

## pick / hook (repeat + bank stock)
```
[pick] stock quiz: 92/464 fresh (~23.0 din)
[pick] stock paheli: 37/158 fresh (~37.0 din)
[pick] भारत/g365: संविधान सभा ने भारतीय संविधान किस दिन अंगीकृत किया?
[hook] on-screen: क्या आप सही जवाब दे पाएंगे?
```

## voice
```
[tts] Gemini key#1 -> 429 daily quota khatam, is run me band
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini bad response (key#2): 'content'
[tts] Gemini key#2 -> 429, 43s cooldown, agli key/retry
[tts] Gemini: sab keys 429 — 43s ruk rahe hain
🎙  voice: elevenlabs, gemini
```

## telegram
```
telegram: sent (http 200)
```
