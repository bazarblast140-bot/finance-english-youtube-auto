"""Run ka state (used.json, uploads.json, LAST_RUN.md, insights) repo me
push karo — retry + merge ke saath.

KYUN: 30-Sep-2026 (run 36713626490) upload ho gaya, par `git push` par GitHub
ne 500 (Internal Server Error) diya. used.json push nahi hua, to agle hi do
run ne wahi sawaal (g005, g135) dobara utha liye — ek din me repeat video.
Pehle `git pull --rebase --autostash || true; git push` ek hi try tha, aur
do run saath chalein to used.json par rebase conflict bhi `|| true` me chhup
jaata tha.

Ab: humne is run me jo JODA (naye used entries, naye/badle ledger rows) wo
memory me rakhte hain, phir har attempt par remote branch ka taaza state lekar
UPAR se merge karte hain aur push karte hain. Conflict aa hi nahi sakta
(text merge nahi, JSON merge), aur 500/non-fast-forward par backoff ke saath
dobara try. Sab attempt fail to exit 1 (job laal, GitHub mail).

Sirf CI (actions/checkout ki working copy) me chalao — ye `git reset --hard`
karta hai.

`--extra data/trends.json` koi aur file bhi isi retry se push hoti hai
(trend research). `--text-files false` LAST_RUN / insights ko is run se
mat chhedo — warna research job upload ke naye LAST_RUN ko purane copy se
overwrite kar sakti hai.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent          # kids-quiz-shorts/
USED = "data/used.json"
LEDGER = "data/uploads.json"
TEXT_FILES = ["LAST_RUN.md", "data/competitor_insights.json"]


def git(*args, check=True, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd or HERE, check=check,
                          capture_output=True, text=True)


def _show(rev_path):
    r = git("show", rev_path, check=False)
    return r.stdout if r.returncode == 0 else None


def _load(text, default):
    try:
        return json.loads(text) if text else default
    except json.JSONDecodeError:
        return default


# ------------------------------------------------------------ pure merges
def new_used_entries(base, ours):
    """ours.history me jo base me nahi tha (is run ne joda)."""
    seen = {(h.get("id"), h.get("at")) for h in base.get("history", [])}
    return [h for h in ours.get("history", []) if (h.get("id"), h.get("at")) not in seen]


def merge_used(remote, added):
    out = {**remote, "history": list(remote.get("history", []))}
    seen = {(h.get("id"), h.get("at")) for h in out["history"]}
    for h in added:
        if (h.get("id"), h.get("at")) not in seen:
            out["history"].append(h)
            seen.add((h.get("id"), h.get("at")))
    return out


def changed_ledger_rows(base, ours):
    """Naye rows + wo purane rows jinme is run ne kuch badla (comment_posted...)."""
    by = {r.get("video_id"): r for r in base if isinstance(r, dict)}
    return [r for r in ours if isinstance(r, dict) and by.get(r.get("video_id")) != r]


def merge_ledger(remote, changed):
    out = [dict(r) for r in remote if isinstance(r, dict)]
    idx = {r.get("video_id"): i for i, r in enumerate(out)}
    for r in changed:
        i = idx.get(r.get("video_id"))
        if i is None:
            idx[r.get("video_id")] = len(out)
            out.append(dict(r))
        else:
            merged = dict(out[i])
            merged.update({k: v for k, v in r.items() if v is not None})
            out[i] = merged
    return out


def normalize_extra(rel: str) -> str:
    """Repo-relative path under kids-quiz-shorts/. `..` aur absolute mana."""
    rel = (rel or "").strip().replace("\\", "/")
    if rel.startswith("./"):
        rel = rel[2:]
    parts = []
    for p in rel.split("/"):
        if p in ("", "."):
            continue
        if p == "..":
            raise SystemExit(f"[sync] extra path mana hai: {rel}")
        parts.append(p)
    if not parts:
        raise SystemExit("[sync] extra path khaali hai")
    rel = "/".join(parts)
    dest = (HERE / rel).resolve()
    root = HERE.resolve()
    if dest != root and root not in dest.parents:
        raise SystemExit(f"[sync] extra path mana hai: {rel}")
    return rel


# ------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default="main")
    ap.add_argument("--message", required=True)
    ap.add_argument("--include-used", choices=["true", "false"], default="false",
                    help="true sirf tab jab upload sach me hua ho")
    ap.add_argument("--text-files", choices=["true", "false"], default="true",
                    help="false = LAST_RUN.md aur insights ko is run se mat chhedo")
    ap.add_argument("--extra", action="append", default=[],
                    help="aur file (kids-quiz-shorts/ se relative), jaise data/trends.json")
    ap.add_argument("--attempts", type=int, default=5)
    a = ap.parse_args(argv)

    prefix = git("rev-parse", "--show-prefix").stdout.strip()      # "kids-quiz-shorts/"
    ours_used = _load((HERE / USED).read_text(encoding="utf-8") if (HERE / USED).exists() else "", {"history": []})
    base_used = _load(_show(f"HEAD:{prefix}{USED}"), {"history": []})
    added_used = new_used_entries(base_used, ours_used) if a.include_used == "true" else []
    ours_led = _load((HERE / LEDGER).read_text(encoding="utf-8") if (HERE / LEDGER).exists() else "", [])
    base_led = _load(_show(f"HEAD:{prefix}{LEDGER}"), [])
    changed_led = changed_ledger_rows(base_led, ours_led)
    texts = {}
    if a.text_files == "true":
        texts = {f: (HERE / f).read_text(encoding="utf-8") for f in TEXT_FILES if (HERE / f).exists()}
    extras = {}
    for rel in a.extra or []:
        rel = normalize_extra(rel)
        p = HERE / rel
        if p.is_file():
            extras[rel] = p.read_text(encoding="utf-8")
    print(f"[sync] used +{len(added_used)}, ledger ~{len(changed_led)}, "
          f"files {sorted(texts)}, extra {sorted(extras)}")

    for attempt in range(1, a.attempts + 1):
        try:
            git("fetch", "--quiet", "origin", a.branch)
            git("reset", "--quiet", "--hard", f"origin/{a.branch}")
            remote_used = _load((HERE / USED).read_text(encoding="utf-8") if (HERE / USED).exists() else "", {"history": []})
            (HERE / USED).write_text(json.dumps(merge_used(remote_used, added_used),
                                                ensure_ascii=False, indent=1), encoding="utf-8")
            remote_led = _load((HERE / LEDGER).read_text(encoding="utf-8") if (HERE / LEDGER).exists() else "", [])
            if changed_led or (HERE / LEDGER).exists():
                (HERE / LEDGER).write_text(json.dumps(merge_ledger(remote_led, changed_led),
                                                      ensure_ascii=False, indent=1), encoding="utf-8")
            for f, t in texts.items():
                (HERE / f).write_text(t, encoding="utf-8")
            for rel, text in extras.items():
                dest = HERE / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text, encoding="utf-8")
            add_paths = [USED]
            for f in [LEDGER, *texts, *extras]:
                if (HERE / f).exists():
                    add_paths.append(f)
            git("add", "--", *add_paths)
            if git("diff", "--staged", "--quiet", check=False).returncode == 0:
                print("[sync] kuch badla nahi — push ki zaroorat nahi")
                return 0
            git("commit", "--quiet", "-m", a.message)
            git("push", "--quiet", "origin", f"HEAD:{a.branch}")
            print(f"[sync] pushed (attempt {attempt})")
            return 0
        except subprocess.CalledProcessError as e:
            err = (e.stderr or e.stdout or "").strip().splitlines()[-1:] or ["?"]
            wait = min(60, 5 * 2 ** (attempt - 1))
            print(f"[sync] attempt {attempt}/{a.attempts} fail: {err[0][:200]} — {wait}s baad dobara")
            if attempt < a.attempts:
                time.sleep(wait)
    print("::error::git push nahi hua — used.json, uploads.json, ya trend files remote par nahi gaye. "
          "LAST_RUN/used.json manually check karo.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
