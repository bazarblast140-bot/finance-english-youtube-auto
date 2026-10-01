"""Trending topic ke liye NAYe sawaal — sirf review file.

    python src/propose_questions.py
    python src/propose_questions.py --dry-run

data/question_candidates.json live bank NAHI hai. questions.json mein kuch
auto-add nahi hota. Fact yahan curated list se aata hai (famous / exam GK),
aur sirf tab jab trend ka keyword usse match kare aur bank mein wahi sawaal
pehle se na ho.

Trend jis topic ko bank bilkul cover nahi karta, uske liye sirf ek gap note
likhte hain — anumanit jawab nahi. Current-affairs ka galat fact yahan se
channel par nahi jaana chahiye.

status `needs_review` agle run mein overwrite ho sakta hai.
`approved` / `rejected` / `edited` rakkha jaata hai.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone

import trend_research as tr
from config import DATA

CANDIDATES_PATH = DATA / "question_candidates.json"
BANK_PATH = DATA / "questions.json"

POLICY = (
    "REVIEW ONLY. Ye file live question bank nahi hai. "
    "data/questions.json mein kuch auto-add nahi hota. "
    "status needs_review wali line agle run mein dubara likhi ja sakti hai. "
    "Rakhna ho to status approved, rejected, ya edited kar do. "
    "Fact dobara check karke hi bank mein haath se daalo."
)

# Famous / exam facts. Har entry verify ki hui hai; phir bhi review ke bina
# bank mein mat daalna. Match terms tabhi catalog se sawaal banate hain jab
# koi keyword-topic unhe contain kare — sirf "भारत" subject se saari list nahi.
CATALOG = [
    {
        "catalog_id": "rbi-1935",
        "sub": "भारत",
        "match": ["rbi", "रिज़र्व बैंक", "रिजर्व बैंक"],
        "q": "भारतीय रिज़र्व बैंक की स्थापना कब हुई?",
        "opts": ["1935", "1947", "1950", "1969"],
        "ans": 0,
        "why": "RBI की स्थापना 1 अप्रैल 1935 को हुई थी।",
    },
    {
        "catalog_id": "niti-2015",
        "sub": "भारत",
        "match": ["niti", "नीति आयोग"],
        "q": "नीति आयोग का गठन किस वर्ष हुआ?",
        "opts": ["2014", "2015", "2016", "2017"],
        "ans": 1,
        "why": "1 जनवरी 2015 को योजना आयोग की जगह नीति आयोग आया।",
    },
    {
        "catalog_id": "fundamental-duties-42",
        "sub": "भारत",
        "match": ["fundamental duties", "मूल कर्तव्य"],
        "q": "भारतीय संविधान में मूल कर्तव्य किस संशोधन से जोड़े गए?",
        "opts": ["42वें", "44वें", "73वें", "86वें"],
        "ans": 0,
        "why": "42वें संशोधन, 1976, में दस मूल कर्तव्य जोड़े गए।",
    },
    {
        "catalog_id": "constituent-assembly-chair",
        "sub": "भारत",
        "match": ["constituent assembly", "संविधान सभा"],
        "q": "संविधान सभा के स्थायी अध्यक्ष कौन थे?",
        "opts": ["डॉ. राजेंद्र प्रसाद", "डॉ. बी. आर. अंबेडकर", "जवाहरलाल नेहरू", "सच्चिदानंद सिन्हा"],
        "ans": 0,
        "why": "डॉ. राजेंद्र प्रसाद स्थायी अध्यक्ष चुने गए; सच्चिदानंद सिन्हा अस्थायी अध्यक्ष थे।",
    },
    {
        "catalog_id": "smallest-state-goa",
        "sub": "भारत",
        "topic": "सबसे",
        "match": ["smallest state", "सबसे छोटा राज्य"],
        "q": "क्षेत्रफल में भारत का सबसे छोटा राज्य कौन सा है?",
        "opts": ["सिक्किम", "गोवा", "त्रिपुरा", "नागालैंड"],
        "ans": 1,
        "why": "गोवा क्षेत्रफल में भारत का सबसे छोटा राज्य है।",
    },
    {
        "catalog_id": "supreme-court-seat",
        "sub": "भारत",
        "match": ["supreme court", "सुप्रीम कोर्ट", "सर्वोच्च न्यायालय"],
        "q": "भारत का सर्वोच्च न्यायालय कहाँ स्थित है?",
        "opts": ["मुंबई", "कोलकाता", "नई दिल्ली", "हैदराबाद"],
        "ans": 2,
        "why": "सुप्रीम कोर्ट नई दिल्ली में है।",
    },
    {
        "catalog_id": "mars-red",
        "sub": "विज्ञान",
        "match": ["red planet", "लाल ग्रह", "mars"],
        "q": "किस ग्रह को लाल ग्रह कहा जाता है?",
        "opts": ["शुक्र", "मंगल", "बृहस्पति", "बुध"],
        "ans": 1,
        "why": "मिट्टी में आयरन ऑक्साइड की वजह से मंगल लाल दिखता है।",
    },
    {
        "catalog_id": "heart-chambers",
        "sub": "विज्ञान",
        "match": ["heart chamber", "हृदय", "दिल के कक्ष"],
        "q": "इंसान के हृदय में कितने कक्ष होते हैं?",
        "opts": ["दो कक्ष", "तीन कक्ष", "चार कक्ष", "पाँच कक्ष"],
        "ans": 2,
        "why": "दो अलिंद और दो निलय — कुल चार कक्ष।",
    },
    {
        "catalog_id": "lightest-metal",
        "sub": "विज्ञान",
        "topic": "सबसे",
        "match": ["lightest metal", "सबसे हल्की धातु", "lithium", "लिथियम"],
        "q": "सबसे हल्की धातु कौन सी है?",
        "opts": ["लोहा", "लिथियम", "सोना", "पारा"],
        "ans": 1,
        "why": "लिथियम सबसे हल्की धातु है — इसका घनत्व पानी से भी कम होता है।",
    },
    {
        "catalog_id": "smallest-continent",
        "sub": "दुनिया",
        "topic": "सबसे",
        "match": ["smallest continent", "सबसे छोटा महाद्वीप"],
        "q": "दुनिया का सबसे छोटा महाद्वीप किसे माना जाता है?",
        "opts": ["यूरोप", "ऑस्ट्रेलिया", "अंटार्कटिका", "दक्षिण अमेरिका"],
        "ans": 1,
        "why": "ऑस्ट्रेलिया सातों महाद्वीपों में क्षेत्रफल के हिसाब से सबसे छोटा है।",
    },
    {
        "catalog_id": "nobel-countries",
        "sub": "दुनिया",
        "match": ["nobel", "नोबेल"],
        "q": "नोबेल पुरस्कार किन देशों में दिए जाते हैं?",
        "opts": ["नॉर्वे और स्वीडन", "स्विट्ज़रलैंड", "अमेरिका", "ब्रिटेन"],
        "ans": 0,
        "why": "शांति पुरस्कार ओस्लो (नॉर्वे) में, बाकी स्टॉकहोम (स्वीडन) में दिए जाते हैं।",
    },
    {
        "catalog_id": "paheli-nayan",
        "sub": "पहेली",
        "match": ["नयन", "palindrome"],
        "q": "तीन अक्षर का मेरा नाम, उल्टा पढ़ो तो भी वही — वो क्या है?",
        "opts": ["नयन", "कमल", "सूरज", "बादल"],
        "ans": 0,
        "why": "नयन को उल्टा पढ़ो तो भी नयन ही रहता है।",
    },
    {
        "catalog_id": "paheli-mushroom-room",
        "sub": "पहेली",
        "match": ["मशरूम", "mushroom"],
        "q": "कौन सा कमरा है जिसमें न खिड़की है न दरवाज़ा?",
        "opts": ["मशरूम", "गुफा", "तिजोरी", "लिफ़ाफ़ा"],
        "ans": 0,
        "why": "मशरूम शब्द में 'रूम' छिपा है — न खिड़की, न दरवाज़ा।",
    },
]


def topic_matches_term(topic: str, term: str) -> bool:
    """Term topic ke andar ho. Ulta (chhota topic, bada term) match nahi — 'संविधान' se 'संविधान सभा' na khule."""
    t = (topic or "").casefold().strip()
    m = (term or "").casefold().strip()
    if len(m) < 3 or len(t) < 3:
        return False
    if re.search(r"[a-z]", m):
        return re.search(rf"(?<![a-z0-9]){re.escape(m)}(?![a-z0-9])", t) is not None
    return m in t


def overlaps_bank(candidate: dict, bank, threshold: float = 0.5) -> bool:
    """pick.load_bank jaisa: same jawab + aadhe se zyada shabd overlap."""
    try:
        ans = candidate["opts"][candidate["ans"]]
    except (KeyError, IndexError, TypeError):
        return False
    cwords = frozenset((candidate.get("q") or "").split())
    for q in bank:
        if not isinstance(q, dict):
            continue
        try:
            bans = q["opts"][q["ans"]]
        except (KeyError, IndexError, TypeError):
            continue
        if bans != ans:
            continue
        bwords = frozenset((q.get("q") or "").split())
        ov = len(bwords & cwords) / max(1, min(len(bwords), len(cwords)))
        if ov >= threshold:
            return True
    return False


def bank_mentions(bank, topic: str) -> int:
    needle = (topic or "").casefold().strip()
    if len(needle) < 3:
        return 0
    n = 0
    for q in bank:
        if not isinstance(q, dict):
            continue
        blob = f"{q.get('q') or ''} {' '.join(q.get('opts') or [])} {q.get('topic') or ''}".casefold()
        if needle in blob:
            n += 1
    return n


def _paheli_hot(topics) -> bool:
    subs = [t for t in topics if isinstance(t, dict) and t.get("kind") == "subject"]
    peak = max((float(t.get("score") or 0) for t in subs), default=0.0) or 1.0
    for t in subs:
        if t.get("topic") == "पहेली" and float(t.get("score") or 0) / peak >= 0.3:
            return True
    for t in topics:
        if not isinstance(t, dict) or t.get("kind") != "keyword":
            continue
        name = (t.get("topic") or "").casefold()
        if "पहेली" in name or "paheli" in name:
            return True
    return False


def _matched_topic(entry, topics):
    for t in topics:
        if not isinstance(t, dict) or t.get("kind") != "keyword":
            continue
        if any(topic_matches_term(t.get("topic") or "", term) for term in entry["match"]):
            return t
    return None


def make_candidate(entry, matched, now: datetime) -> dict:
    day = tr._to_utc(now).date().isoformat()
    iso = tr._to_utc(now).isocalendar()
    row = {
        "catalog_id": entry["catalog_id"],
        "id": f"cand-{iso.year}{iso.week:02d}-{entry['catalog_id']}",
        "status": "needs_review",
        "add_to_bank": False,
        "source": "curated_famous_fact",
        "sub": entry["sub"],
        "q": entry["q"],
        "opts": list(entry["opts"]),
        "ans": entry["ans"],
        "why": entry["why"],
        "trend_topic": None if not matched else matched.get("topic"),
        "trend_score": None if not matched else matched.get("score"),
        "proposed_on": day,
        "note": "REVIEW ONLY. Live bank mein auto-add nahi. Fact check karke haath se daalo.",
    }
    if entry.get("topic"):
        row["topic"] = entry["topic"]
    return row


def select_proposals(trends, bank, now=None, catalog=None, limit=8):
    now = now or datetime.now(timezone.utc)
    catalog = CATALOG if catalog is None else catalog
    topics = [t for t in (trends or {}).get("topics") or [] if isinstance(t, dict)]
    paheli_hot = _paheli_hot(topics)
    candidates = []
    seen = set()
    for entry in catalog:
        if entry["catalog_id"] in seen:
            continue
        matched = _matched_topic(entry, topics)
        if entry["sub"] == "पहेली":
            if not paheli_hot and matched is None:
                continue
        elif matched is None:
            continue
        if overlaps_bank(entry, bank):
            continue
        seen.add(entry["catalog_id"])
        candidates.append(make_candidate(entry, matched, now))
        if len(candidates) >= limit:
            break
    covered = set()
    for entry in catalog:
        for term in entry["match"]:
            covered.add(term.casefold())
    gaps = []
    for t in topics:
        if t.get("kind") != "keyword":
            continue
        name = (t.get("topic") or "").strip()
        if len(name) < 3 or name.casefold() in tr.KEYWORD_STOP:
            continue
        if any(topic_matches_term(name, term) for term in covered):
            continue
        if bank_mentions(bank, name):
            continue
        gaps.append({
            "topic": name,
            "score": t.get("score"),
            "sources": t.get("sources") or [],
            "note": (
                "Bank mein is topic ka seedha sawaal nahi mila, aur curated list mein bhi nahi. "
                "Yahan koi anumanit sawaal nahi likha — khud verify karke likho."
            ),
        })
        if len(gaps) >= 8:
            break
    return candidates, gaps


def merge_proposals(previous, candidates, gaps, now: datetime) -> dict:
    prev_rows = []
    if isinstance(previous, dict):
        prev_rows = [r for r in (previous.get("candidates") or []) if isinstance(r, dict)]
    prev = {r.get("catalog_id"): r for r in prev_rows if r.get("catalog_id")}
    merged, seen = [], set()
    for row in candidates:
        old = prev.get(row["catalog_id"])
        if old and old.get("status") not in (None, "", "needs_review"):
            merged.append(old)
        else:
            merged.append(row)
        seen.add(row["catalog_id"])
    for cid, old in prev.items():
        if cid in seen:
            continue
        if old.get("status") not in (None, "", "needs_review"):
            merged.append(old)
    return {
        "generated_at": tr._to_utc(now).isoformat(timespec="seconds"),
        "policy": POLICY,
        "candidates": merged,
        "gaps": gaps,
    }


def _sig(doc: dict) -> str:
    body = {"candidates": doc.get("candidates") or [], "gaps": doc.get("gaps") or [], "policy": doc.get("policy")}
    return json.dumps(body, ensure_ascii=False, sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Propose review-only questions for trending topics")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    trends = tr.load_active_trends()
    if not trends:
        print("[propose] trends missing/stale — review file nahi badli")
        return 0
    try:
        bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        print("[propose] questions.json nahi padi")
        return 0
    now = datetime.now(timezone.utc)
    candidates, gaps = select_proposals(trends, bank, now)
    try:
        previous = json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        previous = None
    doc = merge_proposals(previous, candidates, gaps, now)
    if not doc["candidates"] and not doc["gaps"]:
        prev_has = bool(previous and (previous.get("candidates") or previous.get("gaps")))
        if not prev_has:
            print("[propose] kuch propose nahi hua")
            return 0
    if previous and _sig(previous) == _sig(doc):
        print("[propose] koi badlav nahi")
        return 0
    print(f"[propose] candidates={len(doc['candidates'])} gaps={len(doc['gaps'])}")
    if args.dry_run:
        print("[propose] dry-run — file nahi likhi")
        return 0
    CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES_PATH.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tr.add_manifest_line("data/question_candidates.json")
    print("[propose] wrote data/question_candidates.json (review only, bank mein add nahi)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[propose] error: {type(e).__name__}: {str(e)[:200]}")
        sys.exit(1)
