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


def pick(n=2, dry_run=False, seed=None, slot="morning"):
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

    # Paheli slot: sirf riddles. Baaki 4 slot GK/Science/Maths/English rotate
    # karte hain aur paheli bank ko chhoote nahi — warna riddle jaldi khatam.
    from config import QUIZ_SLOTS, PAHELI_SUB

    if slot == "paheli":
        pool = [q for q in fresh if q.get("sub") == PAHELI_SUB]
        if len(pool) < n:
            pool = [q for q in bank if q.get("sub") == PAHELI_SUB]
            rng.shuffle(pool)
        chosen = pool[:n]
        if not dry_run:
            stamp = datetime.now().isoformat(timespec="seconds")
            used["history"] += [{"id": q["id"], "at": stamp} for q in chosen]
            USED.write_text(json.dumps(used, ensure_ascii=False, indent=1), encoding="utf-8")
        return chosen

    fresh = [q for q in fresh if q.get("sub") != PAHELI_SUB]

    # Subject rotation: har video me 2 alag subject, aur har slot alag jodi se
    # shuru hota hai — taaki hafte bhar me chaaron subject barabar aayein.
    order = ["सामान्य ज्ञान", "विज्ञान", "भारत", "दुनिया"]
    # Din ka number * quiz-slots + is slot ka index. Paheli is count me nahi,
    # warna 5th slot rotation ko shift kar deta.
    si = QUIZ_SLOTS.index(slot) if slot in QUIZ_SLOTS else 0
    shift = int(datetime.now().strftime("%j")) * len(QUIZ_SLOTS) + si
    wanted = [order[(shift + k) % 4] for k in range(n)]

    chosen, used_now = [], set()
    for want in wanted:
        for q in fresh:
            if q["id"] in used_now:
                continue
            if q.get("sub") == want:
                chosen.append(q)
                used_now.add(q["id"])
                break
    subs_taken = {q.get("sub") for q in chosen}
    for q in fresh:                      # gap bhar do, subject repeat se bachte hue
        if len(chosen) == n:
            break
        if q["id"] not in used_now and q.get("sub") not in subs_taken:
            chosen.append(q); used_now.add(q["id"]); subs_taken.add(q.get("sub"))
    for q in fresh:                      # phir bhi kam pade to kuch bhi
        if len(chosen) == n:
            break
        if q["id"] not in used_now:
            chosen.append(q); used_now.add(q["id"])

    if not dry_run:
        stamp = datetime.now().isoformat(timespec="seconds")
        used["history"] += [{"id": q["id"], "at": stamp} for q in chosen]
        USED.write_text(json.dumps(used, ensure_ascii=False, indent=1), encoding="utf-8")

    return chosen


if __name__ == "__main__":
    from config import SLOT_ORDER
    for slot in SLOT_ORDER:
        print(f"--- {slot} ---")
        for q in pick(2, dry_run=True, slot=slot):
            print(f'  {q["sub"]:<8}| {q["q"]} -> {q["opts"][q["ans"]]}')
