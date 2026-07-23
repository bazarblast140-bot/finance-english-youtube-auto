# Finance English — Faceless YouTube Pipeline

Faceless English finance/investing channel pipeline. Script → Voice → Visuals → Assembly, with a Verify Agent gating every stage, and a daily scheduler.

**Separate from your Hindi Shorts channel.** Different folder, different config, different YouTube token. Never mix them.

---

## THE GOLDEN RULE (read first)

**Do NOT turn on the daily auto-scheduler until 3–5 videos have proven they retain viewers.**

Automation scales whatever you feed it. If the content works, automation makes you 100x. If it doesn't, automation just scales failure — one boring video a day, dragging the channel's signal down. So:

1. Run the pipeline manually (`python run_pipeline.py`).
2. Watch the video. Read the verify report. Fix prompts if needed.
3. Publish manually. **Wait 48 hours. Check the retention graph in YouTube Studio.**
4. Retention decent (viewers staying)? → enable the daily scheduler.
5. Retention bad? → tune the prompts in `prompts/` and `run_*.py`, NOT the plumbing. Repeat.

---

## SETUP (once)

```bash
cd finance-english
cp .env.example .env          # then fill in your keys
pip install -r requirements.txt
```

Edit `config.json`:
- `channel.name`
- keep `pipeline.auto_publish: false` for now

**Voice:** defaults to `voice.engine: "edge"` — free Microsoft neural TTS, no API key,
no per-character cost (same engine the Hindi project uses). To switch to ElevenLabs,
put a key in `.env` and set `voice.engine: "elevenlabs"` + `voice.voice_id`.

Check everything before spending credits:
```bash
python check_setup.py
```

(Optional, nicer text) drop a bold TTF into `assets/fonts/Inter-Bold.ttf`.

---

## RUN ONE VIDEO (manual)

```bash
python run_pipeline.py
```

This runs all stages, stops if any gate fails, writes everything to `run/`, and pings you on Telegram with the verdict.

Outputs in `run/`:
- `script.txt` — the script + FACT LEDGER
- `voice.mp3` — the narration
- `shots.json` — the timed shot list
- `final.mp4` — the assembled video
- `report.md` — the Hinglish verify report (verdict + what you must review)

Review → if good, publish manually (upload `final.mp4` yourself), or:
```bash
python publish.py --only-if-ready    # uploads PRIVATE, only if verdict == READY
```

---

## GO DAILY (after 3–5 good videos)

**GitHub Actions:** the workflow in `.github/workflows/` is already wired for this
folder as the repo root. Add repo Secrets
(`ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`),
and it runs every day at 06:30 IST. Still generate-only (no auto-publish).
It commits `topic_bank.json` back after each run so topics never repeat.

**VPS cron:** see `SCHEDULER.md`.

To later allow auto-publish: set `config.json → pipeline.auto_publish: true` and add YouTube secrets.
Even then it uploads **private + only if verdict READY** — never instant-public.

---

## FILE MAP

| File | Does |
|---|---|
| `check_setup.py` | preflight: keys, ffmpeg, deps, config TODOs — fails before spending credits |
| `pick_topic.py` | picks next unused topic from `topic_bank.json` |
| `run_script.py` | Script Agent + **Gate 1** (hook, facts, compliance) |
| `run_voice.py` | Voice Agent + Edge TTS / ElevenLabs + **Gate 2** (coverage, length, TTS-safety) |
| `run_visuals.py` | Visual Agent + **Gate 3** (density, numbers, repeats) |
| `run_assembly.py` | FFmpeg: cards + voice + burned subtitles → `final.mp4` |
| `run_verify.py` | **Final Gate** → Hinglish `report.md` |
| `notify.py` | Telegram ping |
| `publish.py` | opt-in YouTube upload (private, only if READY) |
| `run_pipeline.py` | chains all stages, stops on gate fail |
| `prompts/` | full Verify Agent + Worker Agent prompts |

---

## KNOWN v1 LIMITATION (be honest about this)

`run_assembly.py` v1 renders **text/data cards**, not real stock footage or live charts.
It produces a real, publishable video so you can test the pipeline end-to-end today —
but for a competitive finance channel you'll want to upgrade `_make_card()` to pull real
footage (via each shot's `source_asset_query`) and render real charts (matplotlib).
The timing, subtitle, and audio-mux logic already works and won't change.

This is the one place where "good enough to test" ≠ "good enough to win." Upgrade it
once the content formula is validated.
