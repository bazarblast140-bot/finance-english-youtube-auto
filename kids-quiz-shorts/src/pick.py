"""Sawaal chunta hai aur repeat nahi hone deta.

used.json me har use ki hui id + date store hoti hai. Order: kabhi use na hue
(fresh) -> REPEAT_COOLDOWN_DAYS se purane, sabse purana pehle -> majboori me
baaki (WARNING ke saath). Isse repeat hamesha sabse door wala hota hai.
Ek video ke 2 sawaal alag-alag category se aate hain — variety ke liye.

data/trends.json (daily research) sirf FRESH pool ko halka sa aage-peeche
karta hai. Cooldown / LRU nahi badalta. File na ho, kharab ho, ya purani ho
to bilkul purana order.
"""
import json
import random
from datetime import datetime, timedelta

from config import DATA

BANK = DATA / "questions.json"
USED = DATA / "used.json"


def load_bank():
    """Bank padho aur duplicate sawaal turant pakdo.

    Ek baar aisa ho chuka hai: 'किस देश को उगते सूरज का देश कहते हैं?' aur
    'उगते सूरज का देश किसे कहा जाता है?' dono bank me the, aur dono live
    chale gaye. Same jawab + zyada shabd overlap = duplicate."""
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    seen = {}
    for q in bank:
        key = (q["opts"][q["ans"]], frozenset(q["q"].split()))
        for (ans, words), other in seen.items():
            if ans != key[0]:
                continue
            ov = len(words & key[1]) / max(1, min(len(words), len(key[1])))
            if ov >= 0.5:
                print(f"[pick] WARNING duplicate: {other} aur {q['id']} "
                      f"— dono ka jawab '{ans}', {ov:.0%} shabd same")
        seen[key] = q["id"]
    return bank


def load_used():
    if USED.exists():
        return json.loads(USED.read_text(encoding="utf-8"))
    return {"history": []}


def last_used_map(history):
    """id -> sabse recent use ka ISO timestamp."""
    last = {}
    for h in history:
        i, at = h.get("id"), h.get("at", "")
        if i and at >= last.get(i, ""):
            last[i] = at
    return last


def rank_pool(pool, last, rng, now, cooldown_days):
    """(fresh, cooled, hot) lautata hai.

    fresh  = kabhi use nahi hue (shuffle)
    cooled = cooldown se purane, SABSE PURANA pehle (least-recently-used)
    hot    = cooldown ke andar use hue, sabse purana pehle — sirf majboori me

    Pehle paheli pool khatam hote hi poore riddle bank ko random shuffle
    karke uthate the, bina ye dekhe ki kal hi kaunsa gaya tha. Isi wajah se
    "एक थाली में सौ मोती", "मीठा है पर मिठाई नहीं" jaisi paheliyan kuch hi
    din me dobara live ho gayin (public channel par dono do-do baar dikhti hain).
    """
    fresh = [q for q in pool if q["id"] not in last]
    rng.shuffle(fresh)
    used = sorted((q for q in pool if q["id"] in last), key=lambda q: last[q["id"]])
    cutoff = (now - timedelta(days=cooldown_days)).isoformat(timespec="seconds")
    cooled = [q for q in used if last[q["id"]] <= cutoff]
    hot = [q for q in used if last[q["id"]] > cutoff]
    return fresh, cooled, hot


def apply_trend_bias(fresh, rng, now):
    """Fresh list me trend-matching sawaal ko thoda aage lao.

    Cooled/hot ko yahan se nahi guzarte — repeat kabhi trend ki wajah se
    jaldi nahi aata. Trends missing/stale/kharab hon to `fresh` jaisa hai
    waisa hi lautata hai (rank_pool ka shuffle bana rehta hai).
    """
    if not fresh:
        return fresh
    try:
        from trend_research import (TREND_WEIGHT_BONUS, load_active_trends,
                                    question_trend_score, weighted_shuffle)
        trends = load_active_trends(now)
    except Exception as e:  # noqa: BLE001 — bias optional hai, pick rukna nahi chahiye
        print(f"[pick] trends skip: {type(e).__name__}")
        return fresh
    if not trends:
        return fresh
    scores = [question_trend_score(q, trends) for q in fresh]
    if not any(s > 0 for s in scores):
        print("[pick] trends taaza hain, in fresh sawaal me topic match nahi")
        return fresh
    weights = [1.0 + TREND_WEIGHT_BONUS * s for s in scores]
    ordered = weighted_shuffle(fresh, weights, rng)
    print(f"[pick] trend bias: {sum(1 for s in scores if s > 0)}/{len(fresh)} "
          f"fresh match, top {ordered[0]['id']}")
    return ordered


def stock_report(bank, last, n):
    """Kitne din ka FRESH stock bacha hai — LAST_RUN.md / Actions log me dikhta hai."""
    from config import (PAHELI_SUB, PAHELI_SLOTS, QUIZ_SLOTS, ACTIVE_SLOTS,
                        BANK_LOW_DAYS)
    out = []
    for name, is_ph, slots in (("quiz", False, QUIZ_SLOTS), ("paheli", True, PAHELI_SLOTS)):
        per_day = n * len([s for s in slots if s in ACTIVE_SLOTS])
        pool = [q for q in bank if (q.get("sub") == PAHELI_SUB) == is_ph]
        fresh = sum(1 for q in pool if q["id"] not in last)
        days = fresh / per_day if per_day else float("inf")
        line = f"[pick] stock {name}: {fresh}/{len(pool)} fresh" + (
            f" (~{days:.1f} din)" if per_day else " (slot band)")
        if per_day and days < BANK_LOW_DAYS:
            line += (f" — WARNING: {BANK_LOW_DAYS} din se kam. Naye sawaal "
                     "data/questions.json me jodo; tab tak sabse purane sawaal "
                     "(least-recently-used) dobara jaayenge.")
        out.append(line)
    return out


def pick(n=2, dry_run=False, seed=None, slot="morning", now=None):
    from config import (QUIZ_SLOTS, PAHELI_SLOTS, PAHELI_SUB,
                        REPEAT_COOLDOWN_DAYS)
    now = now or datetime.now()
    bank = load_bank()
    used = load_used()
    last = last_used_map(used["history"])
    for line in stock_report(bank, last, n):
        print(line)

    # Seed me slot bhi hona zaroori hai. Pehle sirf date+ghanta tha, jo tab
    # theek tha jab din me ek hi paheli banti thi. GitHub ke late/bunched cron
    # ki wajah se do build ek hi ghante me chal sakte hain — us soorat me dono
    # ko bilkul same sawaal mil jaata (used.json tabhi update hota hai jab
    # pehla upload push kar chuka ho).
    rng = random.Random(seed if seed is not None
                        else now.strftime("%Y%m%d%H") + slot)

    is_paheli = slot in PAHELI_SLOTS
    pool = [q for q in bank if (q.get("sub") == PAHELI_SUB) == is_paheli]
    fresh, cooled, hot = rank_pool(pool, last, rng, now, REPEAT_COOLDOWN_DAYS)
    fresh = apply_trend_bias(fresh, rng, now)
    ordered = fresh + cooled + hot

    if is_paheli:
        # Paheli slots: sirf riddles. Baaki slot paheli bank ko chhoote nahi.
        chosen = ordered[:n]
    else:
        # Subject rotation: har video me alag subject, aur har slot alag jodi
        # se shuru hota hai — taaki hafte bhar me chaaron subject barabar aayein.
        order = ["सामान्य ज्ञान", "विज्ञान", "भारत", "दुनिया"]
        si = QUIZ_SLOTS.index(slot) if slot in QUIZ_SLOTS else 0
        shift = int(now.strftime("%j")) * len(QUIZ_SLOTS) + si
        wanted = [order[(shift + k) % 4] for k in range(n)]
        chosen, taken = [], set()
        # Pehle: wanted subject, sirf fresh/cooled me se
        for want in wanted:
            for q in fresh + cooled:
                if q["id"] not in taken and q.get("sub") == want:
                    chosen.append(q); taken.add(q["id"]); break
        subs_taken = {q.get("sub") for q in chosen}
        for q in fresh + cooled:            # gap bharo, subject repeat se bachte hue
            if len(chosen) >= n:
                break
            if q["id"] not in taken and q.get("sub") not in subs_taken:
                chosen.append(q); taken.add(q["id"]); subs_taken.add(q.get("sub"))
        for q in ordered:                   # phir bhi kam pade to LRU order me kuch bhi
            if len(chosen) >= n:
                break
            if q["id"] not in taken:
                chosen.append(q); taken.add(q["id"])

    hot_ids = {q["id"] for q in hot}
    for q in chosen:
        if q["id"] in hot_ids:
            print(f"[pick] WARNING repeat: {q['id']} pichhli baar {last[q['id']][:10]} "
                  f"ko gaya tha ({REPEAT_COOLDOWN_DAYS} din cooldown ke andar) — "
                  "bank chhota pad raha hai.")
        elif q["id"] in last:
            print(f"[pick] reuse (cooldown poora): {q['id']} last {last[q['id']][:10]}")

    if not dry_run:
        stamp = now.isoformat(timespec="seconds")
        used["history"] += [{"id": q["id"], "at": stamp} for q in chosen]
        USED.write_text(json.dumps(used, ensure_ascii=False, indent=1), encoding="utf-8")
    return chosen


if __name__ == "__main__":
    from config import SLOT_ORDER
    for slot in SLOT_ORDER:
        print(f"--- {slot} ---")
        for q in pick(2, dry_run=True, slot=slot):
            print(f'  {q["sub"]:<8}| {q["q"]} -> {q["opts"][q["ans"]]}')
