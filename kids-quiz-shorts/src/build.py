"""Poora short banata hai: sawaal chuno -> voice -> frames -> audio -> MP4 + SEO JSON.

Sync ka tareeka (ye critical hai):
Har segment ki duration pehle FRAMES me convert hoti hai, phir audio us frame
offset pe rakha jaata hai. Isse video aur audio kabhi drift nahi karte —
dono ka source of truth ek hi number hai (frame count).

Usage:
    python src/build.py --slot morning
    python src/build.py --slot evening --seed 42
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

import config as C
import quality
import render
import sfx
import tts
from seo import build as build_seo


# ---------------------------------------------------------------- audio io
def read_wav(path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        assert w.getsampwidth() == 2, f"{path}: 16-bit WAV chahiye"
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
        sr = w.getframerate()
    a = data.astype(np.float32) / 32768.0
    if sr != C.SAMPLE_RATE:                       # safety resample
        n = int(len(a) * C.SAMPLE_RATE / sr)
        a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)
    return a


def mix(track, clip, at_sample, gain=1.0):
    end = min(at_sample + len(clip), len(track))
    if end > at_sample:
        track[at_sample:end] += clip[: end - at_sample] * gain
    return track


# ---------------------------------------------------------------- plan
ENGINES = []


def _fit_voice(path, dur, limit=7.35):
    """Lambi option-line ko timer ke andar kheench lo (atempo <= 1.8).

    8 second ka countdown tabhi saaf dikhta hai jab segment khud 8s ka ho.
    """
    if dur <= limit or not path or path in ("TICKBED", "DING"):
        return path, dur
    speed = min(1.8, max(1.05, dur / limit))
    out = Path(str(path) + ".fit.wav")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(path),
        "-filter:a", f"atempo={speed:.3f}",
        "-ar", str(C.SAMPLE_RATE), "-ac", "1", str(out),
    ], check=True)
    return out, tts.audio_duration(out)


def _seg(kind, dur, voice, audio, payload, **extra):
    item = dict(kind=kind, dur=dur, voice=voice, audio=audio, payload=payload)
    item.update(extra)
    return item


def plan_segments(questions, hook=None):
    """Segments: hook (~2s) -> har sawaal read+8s timer+reveal -> comment CTA.

    Beech ka "ab suniye jawab" hata diya — wo sirf wait badhata tha. Comment
    CTA video ke END mein hai (screen + voice). Options timer ke dauran bolte hain.
    """
    ENGINES.clear()
    segs = []
    n = len(questions)

    if hook:
        v, d, eng = tts.say(tts.hook_script(hook), "hook")
        ENGINES.append(eng)
        print(f"[voice] hook {d:.2f}s via {eng}")
        segs.append(_seg("hook", max(float(C.HOOK_SECONDS), d + 0.12), d,
                         [(0.0, v, C.VOICE_VOLUME)],
                         (questions[0], 1, n), hook=hook))

    for i, q in enumerate(questions):
        v, d, eng = tts.say(tts.question_script(q, i, n), f"q{i}_{q['id']}")
        ENGINES.append(eng)
        print(f"[voice] Q{i+1} {d:.2f}s via {eng}")
        segs.append(_seg("read", d + C.READ_PAD_SECONDS, d,
                         [(0.0, v, C.VOICE_VOLUME)], (q, i + 1, n)))

        # Options timer ke DAURAN. Bolne mein 8s se zyada lage to segment
        # utna lamba — countdown phir bhi aakhri 8 second ka hai.
        ov, od, oeng = tts.say(tts.options_script(q), f"o{i}_{q['id']}")
        ov, od = _fit_voice(ov, od, limit=7.35)
        ENGINES.append(oeng)
        tdur = max(float(C.TIMER_SECONDS), od + 0.35)
        print(f"[voice] Q{i+1} options {od:.2f}s via {oeng} -> timer segment {tdur:.2f}s")
        segs.append(_seg("timer", tdur, od,
                         [(0.0, "TICKBED", C.TICK_VOLUME), (0.0, ov, C.VOICE_VOLUME)],
                         (q, i + 1, n)))

        if C.FAUJI_CTA:
            cv, cd, ceng = tts.say(tts.cta_script(), "cta")
            ENGINES.append(ceng)
            segs.append(_seg("fauji", cd + 0.35, cd,
                             [(0.0, cv, C.VOICE_VOLUME)], (q, i + 1, n)))

        if C.HINT_BEFORE_ANSWER:
            hv, hd, heng = tts.say(tts.hint_script(q), f"h{i}_{q['id']}")
            ENGINES.append(heng)
            segs.append(_seg("hint", hd + 0.4, hd,
                             [(0.0, hv, C.VOICE_VOLUME)], (q, i + 1, n)))

        v, d, eng = tts.say(tts.answer_script(q), f"a{i}_{q['id']}")
        ENGINES.append(eng)
        segs.append(_seg("reveal", max(C.REVEAL_SECONDS, d + 0.45), d,
                         [(0.0, "DING", 0.8), (0.45, v, C.VOICE_VOLUME)],
                         (q, i + 1, n)))

    cv, cd, ceng = tts.say(tts.comment_cta_script(), "comment")
    ENGINES.append(ceng)
    print(f"[voice] comment CTA {cd:.2f}s via {ceng}")
    segs.append(_seg("comment", max(float(C.COMMENT_CTA_SECONDS), cd + 0.15), cd,
                     [(0.0, cv, C.VOICE_VOLUME)], (questions[-1], n, n)))

    for s in segs:
        s["frames"] = max(1, round(s["dur"] * C.FPS))
    return segs


def tighten(segs, limit):
    """Voice ke baad ka khali hissa kaato. Bolti hui line mat kaato.
    Timer 8s se neeche nahi jaata."""
    def total():
        return sum(s["frames"] for s in segs) / C.FPS

    if total() <= limit:
        return total()
    need = total() - limit
    for kind in ("comment", "reveal", "read", "hook"):
        if need <= 0.05:
            break
        for sg in segs:
            if sg["kind"] != kind or need <= 0.05:
                continue
            cur = sg["frames"] / C.FPS
            floor = sg.get("voice", 0.0) + 0.1
            if kind == "hook":
                floor = max(floor, min(float(C.HOOK_SECONDS), cur))
            cut = min(need, max(0.0, cur - floor))
            if cut > 0:
                sg["frames"] = max(1, round((cur - cut) * C.FPS))
                need -= cut
    return total()


# ---------------------------------------------------------------- render
def hook_seed(questions, slot, date=None, nonce=0) -> str:
    date = date or datetime.now()
    qid = questions[0]["id"] if questions else "x"
    return f"{date:%Y%m%d}|{slot}|{qid}|{nonce}"


_HOOK_SYSTEM = (
    "You write ONE Hindi hook line for an adult general-knowledge YouTube Short. "
    "Natural spoken Hindi, not a keyword list. Aap register (बताइए / सोचिए / कीजिए), "
    "never tum (करो / बताओ). No kid or school words. No percentages or invented "
    "statistics. Do not use any forbidden word and do not reveal the answer. "
    "Under 14 words. Curiosity. Reply with JSON only: {\"hook\":\"...\"}"
)


def _parse_hook_reply(raw: str) -> str:
    data = quality._parse_json_blob(raw)
    if isinstance(data, dict):
        return str(data.get("hook") or "").strip()
    return ""


def hook_line(questions, slot, date=None, nonce=0, live=None, complete=None):
    """Pehle ~2 second: natural line, jawab ke bina.

    Live upload DeepSeek se ek line maangta hai. Key na ho, offline ho,
    ya model kharab line de, to offline template.
    """
    if not getattr(C, "HOOK_ON_SCREEN", False) or not questions:
        return None
    q = questions[0]
    is_ph = slot in C.PAHELI_SLOTS or any(item.get("sub") == C.PAHELI_SUB for item in questions)
    template = quality.offline_hook(q, paheli=is_ph)
    if live is None:
        live = os.environ.get("QUIZ_QUALITY_OFFLINE") != "1" and bool(os.environ.get("DEEPSEEK_API_KEY"))
    fn = complete
    if fn is None and live:
        fn = quality.deepseek_complete
    if fn is None:
        return template
    opts = list(q.get("opts") or [])
    ans = q.get("ans")
    forbidden = []
    if isinstance(ans, int) and not isinstance(ans, bool) and 0 <= ans < len(opts):
        forbidden.append(opts[ans])
    payload = json.dumps({
        "question": q.get("q"),
        "subject": q.get("sub"),
        "forbidden": forbidden,
    }, ensure_ascii=False)
    try:
        line = _parse_hook_reply(fn(_HOOK_SYSTEM, payload))
    except (quality.FactCheckError, json.JSONDecodeError, ValueError, TypeError):
        return template
    if quality.accept_hook(line, q):
        return line
    return template


def _save_still(stills_dir, name, img):
    if stills_dir is None:
        return
    stills_dir.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(stills_dir / f"{name}.png")


def _write_frame(frames_dir, idx, img):
    img.convert("RGB").save(frames_dir / f"f{idx:06d}.jpg", quality=92)
    return idx + 1


def _hardlink_rest(frames_dir, first_idx, nf):
    """Pehla frame already likha hai. Baaki usi ki hardlink."""
    first = frames_dir / f"f{first_idx:06d}.jpg"
    idx = first_idx + 1
    for _ in range(nf - 1):
        dst = frames_dir / f"f{idx:06d}.jpg"
        try:
            dst.hardlink_to(first)
        except OSError:
            shutil.copyfile(first, dst)
        idx += 1
    return idx


def render_video(segs, frames_dir: Path, stills_dir: Path | None = None):
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    idx = 0
    saved = set()
    for s in segs:
        kind, payload, nf = s["kind"], s["payload"], s["frames"]
        q, qn, tot = payload

        if kind == "hook":
            base = render.hook_panel(s.get("hook") or "", (q or {}).get("q") or "")
            _save_still(stills_dir, "01_hook", base)
            start = idx
            idx = _write_frame(frames_dir, idx, base)
            idx = _hardlink_rest(frames_dir, start, nf) if nf > 1 else idx
        elif kind == "reveal":
            for f in range(nf):
                progress = 0.0 if nf == 1 else f / (nf - 1)
                img = render.reveal_at(q, qn, tot, progress)
                if stills_dir is not None and "05_reveal" not in saved and progress >= 0.98:
                    _save_still(stills_dir, "05_reveal", img)
                    saved.add("05_reveal")
                if stills_dir is not None and qn == 1 and f == 0:
                    _save_still(stills_dir, "05_reveal_start", img)
                idx = _write_frame(frames_dir, idx, img)
        elif kind == "comment":
            base = render.comment_panel()
            _save_still(stills_dir, "06_comment", base)
            start = idx
            idx = _write_frame(frames_dir, idx, base)
            idx = _hardlink_rest(frames_dir, start, nf) if nf > 1 else idx
        elif kind == "fauji":
            base, region = render.fauji_base(q, qn, tot)
            for f in range(nf):
                img = render.fauji_frame(base, region, f / C.FPS)
                idx = _write_frame(frames_dir, idx, img)
        elif kind == "cta":
            base = render.cta_panel(q, qn, tot)
            start = idx
            idx = _write_frame(frames_dir, idx, base)
            idx = _hardlink_rest(frames_dir, start, nf) if nf > 1 else idx
        elif kind == "hint":
            base = render.hint_panel(q, qn, tot)
            start = idx
            idx = _write_frame(frames_dir, idx, base)
            idx = _hardlink_rest(frames_dir, start, nf) if nf > 1 else idx
        elif kind == "timer":
            base, opt_end = render.question_panel(q, qn, tot)
            seg_secs = nf / C.FPS
            for f in range(nf):
                elapsed = f / C.FPS
                remaining = min(float(C.TIMER_SECONDS), seg_secs - elapsed)
                img = base.copy()
                render.timer_ring(img, remaining, C.TIMER_SECONDS)
                if stills_dir is not None and "03_timer" not in saved and 6.2 <= remaining <= 7.4:
                    _save_still(stills_dir, "03_timer", img)
                    saved.add("03_timer")
                if stills_dir is not None and "04_timer_low" not in saved and 1.6 <= remaining <= 2.6:
                    _save_still(stills_dir, "04_timer_low", img)
                    saved.add("04_timer_low")
                idx = _write_frame(frames_dir, idx, img)
        else:
            # read — chaaron option shuru se. Hook ab alag segment hai.
            base, opt_end = render.question_panel(q, qn, tot)
            if qn == 1:
                _save_still(stills_dir, "02_question", base)
            start = idx
            idx = _write_frame(frames_dir, idx, base)
            idx = _hardlink_rest(frames_dir, start, nf) if nf > 1 else idx
        print(f"[render] {kind:<7} {nf:>4} frames  (total {idx})")
    return idx


def render_audio(segs, total_frames) -> np.ndarray:
    total_samples = int(round(total_frames / C.FPS * C.SAMPLE_RATE))
    track = np.zeros(total_samples, dtype=np.float32)
    ding = sfx.ding()
    frame_cursor = 0
    for s in segs:
        seg_start = int(round(frame_cursor / C.FPS * C.SAMPLE_RATE))
        for off, src, gain in s["audio"]:
            if src == "TICKBED":
                # tick sirf aakhri 8 second me, taaki wo countdown se sync rahe
                seg_secs = s["frames"] / C.FPS
                lead = max(0.0, seg_secs - C.TIMER_SECONDS)
                clip = sfx.build_timer_bed(C.TIMER_SECONDS, 1.0)
                at_extra = int(lead * C.SAMPLE_RATE)
                mix(track, clip, seg_start + at_extra, gain)
                continue
            elif src == "DING":
                clip = ding
            else:
                clip = read_wav(src)
            mix(track, clip, seg_start + int(off * C.SAMPLE_RATE), gain)
        frame_cursor += s["frames"]

    peak = float(np.max(np.abs(track)))
    if peak > 0:
        track = track / peak * 0.92          # normalize, clipping se bacho
    return track


def mux(frames_dir: Path, wav: Path, out_mp4: Path):
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-framerate", str(C.FPS), "-i", str(frames_dir / "f%06d.jpg"),
        "-i", str(wav),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.0",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-movflags", "+faststart", "-shortest",
        str(out_mp4),
    ], check=True)
    return out_mp4


# ---------------------------------------------------------------- gate + main
def _offline_requested(args) -> bool:
    return bool(args.quality_offline or os.environ.get("QUIZ_QUALITY_OFFLINE") == "1")


def prepare(args):
    """Sawaal + hook + voice plan. Gate fail ho to dusra sawaal, phir bhi
    fail ho to report (pass=False). pick.py edit nahi hota."""
    import os
    offline = _offline_requested(args)
    complete = quality.agreeing_complete if offline else quality.deepseek_complete
    trends = quality.load_trends()
    recent = quality.recent_hooks()
    banned = set()
    attempts = 1 if args.ids else 3
    last = None
    ids = [s.strip() for s in (args.ids or "").split(",") if s.strip()]

    for attempt in range(attempts):
        if ids and attempt == 0:
            questions = quality.questions_by_id(ids)
        else:
            if args.seed is not None:
                seed = args.seed + attempt * 17
            elif attempt == 0:
                seed = None          # pick ka rozana seed (date + slot)
            else:
                seed = attempt * 97 + 13
            questions = quality.pick_avoiding(
                C.QUESTIONS_PER_VIDEO, args.slot, banned, seed=seed)
        if len(questions) < 1:
            print("[quality] koi sawaal nahi bacha")
            break
        print("[pick] " + " || ".join(f"{q['sub']}/{q['id']}: {q['q']}" for q in questions))
        hook = hook_line(questions, args.slot, nonce=attempt, live=not offline)
        voice = tts.hook_script(hook) if hook else ""
        if hook:
            print(f"[hook] on-screen+voice: {hook}")
        pre = quality.precheck(questions, hook, voice, trends, complete, recent=recent)
        print(f"[quality] content try {attempt + 1}: "
              f"hook={pre['scores']['hook']} trend={pre['scores']['trend']} "
              f"fact={pre['scores']['fact']} source={(pre.get('fact') or {}).get('source')}")
        for note in pre["notes"].get("fact") or []:
            if str(note).startswith("WARN:"):
                print(f"::warning::{note}")
            print(f"[quality] {note}")
        if not pre["pass_content"]:
            last = pre
            banned |= set(pre.get("bad_ids") or [])
            print(f"[quality] content fail ({pre['reason']}) — doosra sawaal")
            continue

        segs = plan_segments(questions, hook)
        total_dur = tighten(segs, C.LENGTH_MAX_SECONDS)
        print(f"[plan] {len(segs)} segments, {total_dur:.2f}s "
              f"(window {C.LENGTH_MIN_SECONDS:.0f}-{C.LENGTH_MAX_SECONDS:.0f}s)")
        probe = render.visual_probe(questions)
        report = quality.finalize(pre, questions, total_dur, probe)
        last = report
        if report["pass"]:
            return questions, hook, segs, report
        if "visual" in report["failures"]:
            print(f"[quality] visual template fail ({report['reason']}) — sawaal badalne se nahi sudhrega")
            break
        banned |= set(report.get("bad_ids") or [q["id"] for q in questions])
        print(f"[quality] pacing/layout fail ({report['reason']}) — doosra sawaal")

    if last is None:
        last = {"pass": False, "reason": "no questions", "scores": {},
                "notes": {}, "failures": ["fact"], "question_ids": [], "hook": None,
                "fact": {"source": None, "items": [], "bad_ids": []}}
    return None, None, None, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", choices=C.SLOT_ORDER, default="morning")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="sawaal use-history me mat likho (testing ke liye)")
    ap.add_argument("--ids", default=None,
                    help="comma-separated question ids (sample). Fail par swap nahi.")
    ap.add_argument("--out", default=None, help="out/ ke andar folder naam")
    ap.add_argument("--quality-offline", action="store_true",
                    help="DeepSeek ki jagah stored answer se sehmat (sample/CI). Upload par mat use karo.")
    args = ap.parse_args()

    stamp = datetime.now().strftime("%Y%m%d")
    slug = args.out or f"{stamp}_{args.slot}"
    outdir = C.OUT / slug
    outdir.mkdir(parents=True, exist_ok=True)

    questions, hook, segs, report = prepare(args)
    report = quality.stamp(report)
    if questions is None or not report.get("pass"):
        quality.write_report(outdir, report)
        if not args.dry_run:
            quality.append_history(report)
        quality.log_report(report)
        print("[quality] FAIL — upload blocked. Dusra sawaal try ho chuka hai.")
        return 1

    if not args.dry_run:
        quality.commit_used(questions)

    if report["duration_sec"] > C.HARD_LIMIT_SECONDS:
        print(f"[ERROR] {report['duration_sec']:.1f}s — 3 min se lamba, Short nahi banega.")
        return 1

    frames_dir = outdir / "frames"
    stills_dir = outdir / "stills"
    total_frames = render_video(segs, frames_dir, stills_dir=stills_dir)
    track = render_audio(segs, total_frames)
    wav = sfx.write_wav(outdir / "audio.wav", track)

    mp4 = mux(frames_dir, wav, outdir / f"{slug}.mp4")
    shutil.rmtree(frames_dir)

    meta = build_seo(questions, args.slot)
    meta["video_file"] = str(mp4)
    meta["hook_line"] = hook
    meta["subjects"] = [q.get("sub", "GK") for q in questions]
    meta["duration_sec"] = round(total_frames / C.FPS, 2)
    meta["comment_cta"] = C.CTA_TEXT
    # voice_engines metadata WRITE se PEHLE set hona chahiye.
    used = {e.split("+")[0] for e in ENGINES}
    meta["voice_engines"] = sorted(used)
    (outdir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    report["duration_sec"] = meta["duration_sec"]
    # Actual length plan se alag ho to pacing dubara, par voice cut mat karo.
    # Plan hi source of truth hai (frame count). Yahan sirf report update.
    quality.write_report(outdir, report)
    if not args.dry_run:
        quality.append_history(report)
    quality.log_report(report)

    print(f"\n🎙  voice: {', '.join(sorted(used))}"
          + ("  <- ElevenLabs fail hua, free voice pe chala" if "edge" in used else ""))
    print(f"✅ {mp4}  ({meta['duration_sec']}s)")
    print(f"📝 {outdir / 'metadata.json'}")
    print(f"🎬 {meta['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
