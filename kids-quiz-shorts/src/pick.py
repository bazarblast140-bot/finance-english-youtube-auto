"""Sawaal chunta hai aur repeat nahi hone deta.

used.json me har use ki hui id + date store hoti hai. Jab saare sawaal khatam
ho jayein, cycle reset hota hai (sabse purane wale phir se eligible).
Ek video ke 2 sawaal alag-alag category se aate hain — variety ke liye.
"""
import json
import random
from datetime import datetime

from config import DATA

BANK = DATA / "questions.json"
USED = DATA / "used.json"


def load_bank():
    return json.loads(BANK.read_text(encoding="utf-8"))


def load_used():
    if USED.exists():
        return json.loads(USED.read_text(encoding="utf-8"))
    return {"history": []}


def pick(n=2, dry_run=False, seed=None):
    bank = load_bank()
    used = load_used()
    used_ids = [h["id"] for h in used["history"]]
    fresh = [q for q in bank if q["id"] not in used_ids]

    if len(fresh) < n:
        # Cycle poora ho gaya — sabse purane n*6 sawaal wapas eligible kar do
        recycle = used_ids[: max(0, len(used_ids) - n * 6)]
        fresh = [q for q in bank if q["id"] not in used_ids[len(recycle):]]
        print(f"[pick] bank cycle reset — {len(fresh)} sawaal wapas available")

    rng = random.Random(seed if seed is not None else datetime.now().strftime("%Y%m%d%H"))
    rng.shuffle(fresh)

    chosen, cats = [], set()
    for q in fresh:                      # pehle alag category try karo
        if q["cat"] not in cats:
            chosen.append(q)
            cats.add(q["cat"])
        if len(chosen) == n:
            break
    for q in fresh:                      # kam pade to kuch bhi
        if len(chosen) == n:
            break
        if q not in chosen:
            chosen.append(q)

    if not dry_run:
        stamp = datetime.now().isoformat(timespec="seconds")
        used["history"] += [{"id": q["id"], "at": stamp} for q in chosen]
        USED.write_text(json.dumps(used, ensure_ascii=False, indent=1), encoding="utf-8")

    return chosen


if __name__ == "__main__":
    for q in pick(2, dry_run=True):
        print(q["cat"], "|", q["q"], "->", q["opts"][q["ans"]])
