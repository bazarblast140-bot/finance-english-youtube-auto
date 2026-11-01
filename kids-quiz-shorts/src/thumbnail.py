"""Custom Shorts thumbnail / cover (1080x1920) — kabhi auto-frame nahi.

Rajesh order 01-Nov-2026: har Short ka topic thumbnail, bada padhne layak
Hindi text (2-5 shabd), "?" accent, chhota QUIZ PATHSHALA tag, JAWAB KABHI
NAHI. Background = Q1 ka question panel, heavy blur (options padhe na jaa sakein).

    python src/thumbnail.py --backfill            # dry-run: scheduled private list
    python src/thumbnail.py --backfill --apply    # thumbnails.set (sirf wahi)
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import config as C

MAX_WORDS = 5
STOP_END = {"है", "हैं", "था", "थे", "थी", "को", "का", "की", "के", "में", "से",
            "ने", "पर", "और", "एक"}
QWORDS = ("कौन", "किस", "कितन", "क्या", "कहाँ", "कहां", "कब", "कैसे", "किसे", "किन")


def hook_text(q):
    """Sawaal se 2-5 shabd ka hook. Jawab ka koi shabd na ho (leak guard)."""
    words = re.sub(r"[?？!।,'\"‘’“”()]", " ", q["q"]).split()
    ans_words = {w for o in [q["opts"][q["ans"]]] for w in re.sub(r"[?？!।,'\"‘’“”()]", " ", str(o)).split()
                 if len(w) > 1}
    # question-word tak ka hissa sabse acchha topic hai; warna pehle 4
    cut = next((i for i, w in enumerate(words) if w.startswith(QWORDS)), None)
    pick = words[:min(cut + 1, MAX_WORDS)] if cut is not None and cut >= 1 else words[:4]
    pick = [w for w in pick if w not in ans_words]
    while len(pick) > 2 and pick[-1] in STOP_END:
        pick.pop()
    if len(pick) < 2:
        pick = ["पहेली", "बूझिए"] if q.get("sub") == C.PAHELI_SUB else ["GK", "सवाल"]
    text = " ".join(pick[:MAX_WORDS])
    if leaks_answer(text, q):
        text = "पहेली बूझिए" if q.get("sub") == C.PAHELI_SUB else "GK सवाल"
    return text


def leaks_answer(text, q):
    ans = str(q["opts"][q["ans"]]).strip()
    return bool(ans) and len(ans) > 1 and ans in text


def _fit(draw, text, font_fn, max_w, max_h, start=190, min_size=90):
    import render
    size = start
    while size >= min_size:
        f = font_fn(size)
        lines = render.wrap(draw, text, f, max_w)
        lh = int(size * 1.3)
        if len(lines) <= 3 and len(lines) * lh <= max_h and \
                all(render.text_w(draw, l, f) <= max_w for l in lines):
            return f, lines, lh, size
        size -= 6
    f = font_fn(min_size)
    return f, render.wrap(draw, text, f, max_w), int(min_size * 1.3), min_size


def make(q, out_path, n=1):
    import render
    base, _ = render.question_panel(q, 1, n)
    img = base.convert("RGB").filter(ImageFilter.GaussianBlur(28))
    img = Image.blend(img, Image.new("RGB", img.size, (10, 12, 40)), 0.45)
    d = ImageDraw.Draw(img)
    text = hook_text(q)
    assert not leaks_answer(text, q), "thumbnail me jawab!"
    f, lines, lh, size = _fit(d, text, lambda s: render.F(s), C.W - 140, 900)
    top = 560 + (900 - len(lines) * lh) // 2
    stroke = max(8, size // 14)
    for i, line in enumerate(lines):
        w = render.text_w(d, line, f)
        d.text(((C.W - w) // 2, top + i * lh), line, font=f, fill=(255, 230, 40),
               stroke_width=stroke, stroke_fill=(0, 0, 0))
    qf = render.F(420)
    qw = render.text_w(d, "?", qf)
    d.text(((C.W - qw) // 2, top + len(lines) * lh + 10), "?", font=qf,
           fill=(255, 70, 70), stroke_width=14, stroke_fill=(255, 255, 255))
    tf = render.F(54)
    tag = "QUIZ PATHSHALA"
    tw = render.text_w(d, tag, tf)
    d.rounded_rectangle([(C.W - tw) // 2 - 30, 200, (C.W + tw) // 2 + 30, 290],
                        radius=40, fill=(255, 255, 255))
    d.text(((C.W - tw) // 2, 212), tag, font=tf, fill=(20, 24, 70))
    out_path = Path(out_path)
    img.save(out_path, "JPEG", quality=88, optimize=True)
    if out_path.stat().st_size > 2_000_000:     # YouTube limit 2MB
        img.save(out_path, "JPEG", quality=75, optimize=True)
    return {"path": str(out_path), "text": text, "lines": lines, "font_size": size}


def set_thumbnail(yt, video_id, path):
    """thumbnails.set — fail ho to WARNING, exception upar nahi jaata."""
    from googleapiclient.http import MediaFileUpload
    try:
        yt.thumbnails().set(videoId=video_id,
                            media_body=MediaFileUpload(str(path), mimetype="image/jpeg")).execute()
        print(f"[thumb] set OK -> {video_id}")
        return True
    except Exception as e:
        print(f"[thumb] WARNING: thumbnails.set fail ({video_id}): {str(e)[:300]} "
              "— video upload theek hai, sirf custom thumbnail nahi laga. "
              "(Channel phone-verified ho aur token me youtube/youtube.upload scope ho.)")
        return False


def scheduled_private(rows, now=None):
    """Ledger rows jinka publish_at abhi future me hai (private + scheduled)."""
    now = now or datetime.now(timezone.utc)
    out = []
    for r in rows:
        pa = r.get("publish_at")
        if not pa or not r.get("video_id"):
            continue
        try:
            t = datetime.strptime(pa, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if t > now:
            out.append(r)
    return out


def backfill(apply=False, outdir=None):
    from pick import load_bank
    rows = json.loads((C.DATA / "uploads.json").read_text(encoding="utf-8"))
    todo = scheduled_private(rows)
    bank = {q["id"]: q for q in load_bank()}
    outdir = Path(outdir or C.OUT / "thumb_backfill")
    outdir.mkdir(parents=True, exist_ok=True)
    yt = None
    if apply and todo:
        from googleapiclient.discovery import build
        from upload import _creds
        yt = build("youtube", "v3", credentials=_creds(), cache_discovery=False)
    ok = []
    print(f"[backfill] {len(todo)} scheduled video(s), apply={apply}")
    for r in todo:
        vid = r["video_id"]
        qid = (r.get("question_ids") or [None])[0]
        q = bank.get(qid)
        if not q:
            print(f"[backfill] {vid}: question {qid} bank me nahi — skip")
            continue
        if yt is not None:
            # sirf private + scheduled par hi (status read-only check, 1 unit)
            it = yt.videos().list(part="status", id=vid).execute().get("items") or []
            st = it[0]["status"] if it else {}
            if st.get("privacyStatus") != "private" or not st.get("publishAt"):
                print(f"[backfill] {vid}: private+scheduled nahi ({st.get('privacyStatus')}) — skip")
                continue
        info = make(q, outdir / f"{vid}.jpg")
        print(f"[backfill] {vid} publish_at={r['publish_at']} text='{info['text']}'")
        if yt is not None and set_thumbnail(yt, vid, info["path"]):
            ok.append(vid)
    print(f"[backfill] thumbnails set: {', '.join(ok) or '(none)'}")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.backfill:
        backfill(apply=a.apply)
    else:
        ap.error("--backfill do")
