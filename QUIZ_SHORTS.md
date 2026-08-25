# Quiz Shorts (GK-challenge format)

Vertical 9:16 finance quiz videos for **The Money Rule**.

This is a **separate** path from the 4.5-minute long-form pipeline.
`run_pipeline.py` is unchanged. Daily long-form still runs as before.

## What one short looks like

1. Maroon banner: **Finance Challenge for You**
2. Question on cream paper (navy type)
3. Four options A / B / C / D
4. Female voice (`en-IN-NeerjaNeural`) reads the question
5. Tick-tick countdown (default 5 seconds)
6. Correct option turns green; voice reads the answer + one-line fact

Same beat as Hindi GK Shorts — finance questions, English, female voice.

## Render one

```bash
python run_quiz_short.py           # next unused question
python run_quiz_short.py --id q01  # a specific id
```

Needs the same deps as the rest of the repo: `edge-tts`, `Pillow`, `numpy`, `ffmpeg`.

Output: `run/quiz_short.mp4` (1080×1920).

Questions live in `quiz_bank.json`. Used ids are stored in `used_quiz.json` so the next run does not repeat until the bank wraps.

## Voice

Female Indian English neural voice, no API key:

```
en-IN-NeerjaNeural
```

Change it in `quiz_bank.json` → `"voice"`. Do not point this at `hi-IN-MadhurNeural` (male).

## Publish

Upload `run/quiz_short.mp4` as a YouTube **Short**. Keep long-form private-review flow as it is until quiz retention looks good.
