"""Upload se pehle quality gate.

Scores: hook, visual clarity, trend fit, pacing, factual accuracy.
Fact check DeepSeek se hota hai (secret: DEEPSEEK_API_KEY). Call inject karo
(`complete(system, user) -> str`) to tests network ke bina chalte hain.

QUIZ_QUALITY_OFFLINE=1 sirf sample / local render ke liye hai — upload workflow
ise set NAHI karta, aur live path DeepSeek ko sach mein call karta hai.

Fail-safe: upload sirf tab rukta hai jab model confidently disagree kare
(choice != stored ans, ambiguous, ya explanation_ok false) ya structure
tooti ho (4 unique options nahi). Key missing, network, HTTP, empty, ya
unparseable reply sirf WARN hai — upload nahi rukta.

trends.json (data/trends.json) doosri branch se aa sakta hai. File na ho to
trend score neutral hai, fail nahi.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

import config as C

THRESHOLDS = {
    "hook": 70,
    "visual": 70,
    "trend": 60,
    "pacing": 70,
    "fact": 100,
}

KID_SIGNALS = (
    "class 1", "class 5", "कक्षा", "बच्चे", "बच्चों", "kids", "school",
    "homework", "स्कूल", "होमवर्क", "घर वालों",
)
TUM_FORMS = ("करो", "लिखो", "रुको", "बताओ", "पूछो", "खेलो")
CURIOSITY = (
    "सेकंड", "जवाब", "सोच", "पता", "चैलेंज", "बूझ", "दिमाग", "दिमाग़",
    "तैयार", "पक्का", "चुन", "क्या", "कौन", "किस", "कहाँ", "कहां", "क्यों",
    "कितने", "कितना", "बता", "पहेली", "सुलझ",
)
AAP_MARKS = (
    "आप", "आपको", "दीजिए", "बताइए", "सोचिए", "चुनिए", "बूझिए",
    "लगाइए", "कीजिए", "हैं", "सकते",
)

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_SUBJECT_ALIASES = {
    "भारत": ("india", "bharat", "indian"),
    "विज्ञान": ("science", "vigyan"),
    "दुनिया": ("world", "duniya", "world gk"),
    "पहेली": ("paheli", "riddle", "puzzle"),
    "सामान्य ज्ञान": ("gk", "samanya", "general knowledge", "quiz"),
}

FACT_SYSTEM = (
    "You fact-check Hindi general-knowledge multiple-choice questions for adults "
    "(competitive-exam level, not children). "
    "For each question choose the single correct option index (0=A, 1=B, 2=C, 3=D) "
    "from your own knowledge. Ignore the stored ans if it is wrong. "
    "Set ambiguous=true if more than one option is defensibly correct. "
    "Set explanation_ok=true only if the given why is factually right and supports "
    "the correct option. Reply with JSON only, no markdown: "
    '{"items":[{"id":"...","choice":0,"ambiguous":false,"explanation_ok":true,"note":"short"}]}'
)


class FactCheckError(RuntimeError):
    """API/key failure. Message must never contain the API key."""


def structural_issues(q: dict) -> list[str]:
    opts = list(q.get("opts") or [])
    issues = []
    if len(opts) != 4:
        issues.append("exactly 4 options required")
    if len(opts) != len(set(opts)):
        issues.append("options must be unique — exactly one correct choice")
    ans = q.get("ans")
    if not isinstance(ans, int) or isinstance(ans, bool) or ans not in range(len(opts) or 0):
        issues.append("ans must be a single index 0-3")
    if not (q.get("why") or "").strip():
        issues.append("missing why")
    if not (q.get("q") or "").strip():
        issues.append("missing question")
    return issues


# Generic stock lines (config.HOOK_LINES) aur sawaal se be-lagaav teaser
# threshold ke neeche jaate hain. Nakli "90%" claim bhi.
HOOK_STOP = frozenset({
    "क्या", "कौन", "किस", "किसमें", "किसका", "किसकी", "में", "है", "हैं",
    "का", "की", "के", "से", "को", "एक", "यह", "ये", "और", "या", "तो", "जो",
    "वह", "वो", "था", "थी", "कर", "करके", "होता", "होती", "होते", "नहीं",
    "भी", "पर", "लिए", "वाला", "वाली", "आप", "आपको", "सकते", "बता", "सकती",
})
_PERCENT_CLAIM = re.compile(r"\d+\s*%")


def content_tokens(text: str) -> list[str]:
    words = re.findall(r"[\u0900-\u097FA-Za-z0-9]+", text or "")
    return [w for w in words if len(w) >= 2 and w not in HOOK_STOP]


def topic_phrase(q: dict, limit: int = 4) -> str:
    """Sawaal ke topic words, sahi option ke bina (hook spoil na kare)."""
    opts = list(q.get("opts") or [])
    ans = q.get("ans")
    banned: set[str] = set()
    if isinstance(ans, int) and not isinstance(ans, bool) and 0 <= ans < len(opts):
        banned = set(content_tokens(str(opts[ans])))
    words = [w for w in content_tokens(q.get("q") or "") if w not in banned]
    if not words:
        words = content_tokens(q.get("sub") or "") or ["सवाल"]
    return " ".join(words[:limit])


def _stock_hooks() -> set[str]:
    return {" ".join(t.split()) for lines in C.HOOK_LINES.values() for t in lines}


def hook_is_generic(line: str, question=None) -> bool:
    """Stock line, ya sawaal/subject ka koi topic word nahi."""
    norm = " ".join((line or "").split())
    if norm in _stock_hooks():
        return True
    if question is None:
        return False
    if isinstance(question, str):
        blob = question
    else:
        blob = f"{question.get('q', '')} {question.get('sub', '')}"
    qtoks = set(content_tokens(blob))
    if not qtoks:
        return False
    return not (qtoks & set(content_tokens(line)))


def hook_is_keyword_list(line: str) -> bool:
    """'सोचिए — कच्छ रण राज्य' jaisi tooti hui list. Sawal-jaisi line nahi."""
    if "?" in (line or "") or "？" in (line or ""):
        return False
    parts = re.split(r"[—:–\-]", line or "", maxsplit=1)
    tail = parts[-1] if len(parts) > 1 else (line or "")
    words = [w.strip("।,. ") for w in tail.split() if w.strip("।,. ")]
    if len(words) < 3:
        return False
    posts = {"का", "की", "के", "में", "से", "को", "पर", "ने", "कौन", "किस", "कहाँ", "कहां", "क्यों"}
    return not any(w in posts for w in words)


def hook_spoils_answer(line: str, question) -> bool:
    if not isinstance(question, dict):
        return False
    opts = list(question.get("opts") or [])
    ans = question.get("ans")
    if not isinstance(ans, int) or isinstance(ans, bool) or ans not in range(len(opts)):
        return False
    qtoks = set(content_tokens(question.get("q") or ""))
    leaked = [t for t in content_tokens(str(opts[ans])) if t not in qtoks]
    if not leaked:
        return False
    htoks = set(content_tokens(line))
    return any(t in htoks for t in leaked)


def score_hook(line: str, voice: str = "", recent=(), question=None) -> tuple[int, list[str]]:
    notes = []
    line = (line or "").strip()
    if not line:
        return 0, ["empty hook"]
    low = line.lower()
    if any(bad.lower() in low for bad in KID_SIGNALS):
        return 20, ["kid or school wording"]
    if any(tum in line for tum in TUM_FORMS):
        return 25, ["tum-register imperative"]
    score = 0
    if 6 <= len(line) <= 60:
        score += 20
    else:
        score += 8
        notes.append("hook length")
    if any(k in line for k in CURIOSITY):
        score += 25
    else:
        notes.append("no curiosity or challenge")
    if any(mark in line for mark in AAP_MARKS):
        score += 25
    else:
        score += 5
        notes.append("aap register weak")
    if line not in set(recent or ()):
        score += 15
    else:
        score += 4
        notes.append("hook repeated from recent run")
    voice = (voice or "").strip()
    if voice and (line in voice or voice in line):
        score += 15
    elif voice:
        score += 8
        notes.append("voice hook differs from on-screen line")
    else:
        notes.append("hook has no voice line")
    if hook_is_generic(line, question):
        score = min(score, 48)
        notes.append("generic hook — question-specific teaser missing")
    if hook_is_keyword_list(line):
        score = min(score, 46)
        notes.append("keyword-list hook — use a natural line")
    if hook_spoils_answer(line, question):
        score = min(score, 30)
        notes.append("hook names the correct option")
    if _PERCENT_CLAIM.search(line):
        # "90% log galat" tabhi jab yeh sach ho. Hamare paas aisa data nahi,
        # isliye koi percentage claim score giraati hai.
        score = min(score, 40)
        notes.append("unverified percentage claim")
    return min(100, score), notes


_FILLER = frozenset({
    "ये", "यह", "वह", "वो", "ही", "भी", "तो", "एक", "बहुत", "काफी",
})
_SOFT = frozenset({"विशाल", "बड़ा", "छोटा", "पुराना", "नया"})
_ASKS = (
    ("किस राज्य में", "किस राज्य में?"),
    ("किस शहर में", "किस शहर में?"),
    ("किस देश", "किस देश में?"),
    ("कौन सी है", "कौन?"),
    ("कौन सा है", "कौन?"),
    ("कौन सी", "कौन?"),
    ("कौन सा", "कौन?"),
    ("कौन थे", "कौन?"),
    ("कौन थी", "कौन?"),
    ("कौन है", "कौन?"),
    ("कहाँ है", "कहाँ?"),
    ("कहां है", "कहाँ?"),
    ("क्यों", "क्यों?"),
    ("कितने", "कितने?"),
    ("कितना", "कितना?"),
)


def _answer_text(q: dict) -> str:
    opts = list(q.get("opts") or [])
    ans = q.get("ans")
    if isinstance(ans, int) and not isinstance(ans, bool) and 0 <= ans < len(opts):
        return str(opts[ans])
    return ""


def _ask_from_question(q: dict, paheli: bool = False) -> str:
    text = (q.get("q") or "").replace("?", " ").replace("।", " ")
    for needle, ask in _ASKS:
        if needle in text:
            return "बूझिए!" if paheli and ask == "कौन?" else ask
    return "बूझिए!" if paheli else "पता है आपको?"


def _phrase(text: str, limit: int = 5, drop_soft: bool = False) -> str:
    words = []
    for raw in (text or "").replace("।", " ").split():
        w = raw.strip(" ,—–-:;\"'")
        if not w or w in _FILLER or (drop_soft and w in _SOFT):
            continue
        words.append(w)
        if len(words) >= limit:
            break
    while words and words[-1] in {"का", "की", "के", "में", "से", "को", "पर", "ने", "है", "हैं"}:
        words.pop()
    return " ".join(words)


def _lead_before_answer(q: dict) -> str:
    why = (q.get("why") or "").strip()
    ans = _answer_text(q)
    if not why or not ans or ans not in why:
        return ""
    head = why.split(ans, 1)[0]
    for opt in q.get("opts") or []:
        if opt and opt != ans and opt in head:
            head = head.split(opt, 1)[0]
    return head


def _question_hook(q: dict, paheli: bool = False) -> str:
    text = (q.get("q") or "").strip().rstrip("?। ")
    ask = _ask_from_question(q, paheli=paheli)
    head = text
    for needle, _ask in _ASKS:
        if needle in text:
            head = text.split(needle, 1)[0].strip(" ,—–-")
            break
    head = head.rstrip(" ,—–-")
    if not head:
        head = _phrase(text, limit=6) or (q.get("sub") or "ये सवाल")
    line = f"{head} — {ask}"
    if len(line) > 58:
        line = f"{_phrase(head, limit=4)} — {ask}"
    return " ".join(line.split())


def offline_hook(q: dict, paheli: bool = False) -> str:
    """Template jab DeepSeek na ho. Natural line, jawab ka naam nahi.

    'सोचिए — कच्छ रण राज्य' jaisi keyword list nahi. Why ka pehla
    hissa (jawab se pehle) warna khud sawaal ko chhota karke.
    """
    ask = _ask_from_question(q, paheli=paheli)
    lead = _phrase(_lead_before_answer(q), limit=5, drop_soft=True)
    if len(lead.split()) >= 3:
        line = f"{lead} — {ask}"
    else:
        line = _question_hook(q, paheli)
    if hook_spoils_answer(line, q) or any(t in line for t in TUM_FORMS):
        line = _question_hook(q, paheli)
    return " ".join(line.split())


def accept_hook(line: str, question) -> bool:
    """Live model ki line tabhi lo jab wo natural ho aur jawab na khole."""
    line = " ".join((line or "").split())
    if not line or len(line) > 70:
        return False
    low = line.lower()
    if any(bad.lower() in low for bad in KID_SIGNALS):
        return False
    if any(tum in line for tum in TUM_FORMS):
        return False
    if _PERCENT_CLAIM.search(line):
        return False
    if hook_is_generic(line, question) or hook_is_keyword_list(line):
        return False
    if hook_spoils_answer(line, question):
        return False
    score, _notes = score_hook(line, line, question=question)
    return score >= THRESHOLDS["hook"]


def load_trends(path=None):
    path = path or (C.DATA / "trends.json")
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def trend_tokens(trends) -> list[str] | None:
    if trends is None:
        return None
    blobs: list[str] = []
    if isinstance(trends, list):
        blobs = [str(x) for x in trends]
    elif isinstance(trends, dict):
        for key in ("topics", "keywords", "subjects", "titles", "trends", "queries", "tags"):
            val = trends.get(key)
            if isinstance(val, list):
                blobs.extend(str(x) for x in val)
            elif isinstance(val, str):
                blobs.append(val)
        if not blobs:
            blobs = [str(v) for v in trends.values() if isinstance(v, (str, int, float))]
    else:
        blobs = [str(trends)]
    return [b.strip() for b in blobs if str(b).strip()]


def score_trend(questions, trends) -> tuple[int, list[str]]:
    tokens = trend_tokens(trends)
    if tokens is None:
        return 72, ["trends.json absent — neutral, not a fail"]
    if not tokens:
        return 72, ["trends file empty — neutral"]
    blob = " ".join(
        f"{q.get('sub', '')} {q.get('q', '')} {' '.join(q.get('opts') or [])}"
        for q in questions
    ).lower()
    subs = {(q.get("sub") or "") for q in questions}
    hits = []
    for tok in tokens:
        t = tok.lower()
        if t and t in blob:
            hits.append(tok)
            continue
        for sub in subs:
            if t and t in sub.lower():
                hits.append(tok)
                break
            for alias in _SUBJECT_ALIASES.get(sub, ()):
                if alias in t or t in alias:
                    hits.append(tok)
                    break
    if hits:
        return min(100, 74 + 8 * len(set(hits))), [f"trend match: {list(dict.fromkeys(hits))[:4]}"]
    hindi = any(_DEVANAGARI.search(t) for t in tokens)
    if hindi:
        return 42, ["Hindi trends present but this video does not match"]
    return 64, ["latin trends had no subject alias — weak fit, not a hard miss"]


def score_pacing(duration: float) -> tuple[int, list[str]]:
    if duration is None:
        return 0, ["duration unknown"]
    if 30 <= duration <= 40:
        return 100, [f"{duration:.1f}s inside 30-40s"]
    if 26 <= duration <= 45:
        return 78, [f"{duration:.1f}s near the 30-40s window"]
    return 40, [f"{duration:.1f}s outside retention window"]


def score_visual(probe: dict, questions) -> tuple[int, list[str]]:
    notes = []
    if not (probe.get("font_latin") and probe.get("font_devanagari")):
        notes.append("font missing Devanagari or Latin (A-D / QUIZ PATHSHALA)")
        return 30, notes
    score = 25
    if int(probe.get("timer_radius") or 0) >= 96:
        score += 20
    else:
        notes.append("countdown timer too small")
    if int(probe.get("option_font") or 0) >= 52:
        score += 15
    else:
        notes.append("option text too small")
    if probe.get("why_on_reveal") and probe.get("reveal_highlight"):
        score += 15
    else:
        notes.append("answer reveal missing highlight or why")
    if probe.get("comment_cta"):
        score += 15
    else:
        notes.append("comment CTA panel missing")
    import indiamap
    geo = [q["id"] for q in questions if indiamap.for_question(q)]
    mapped = set(probe.get("map_ids") or [])
    if geo and not set(geo) <= mapped:
        notes.append("state/geography question without India map")
        return min(score, 50), notes
    score += 10
    return score, notes


def _parse_json_blob(text: str):
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def fact_payload(questions) -> str:
    slim = [{
        "id": q.get("id"),
        "q": q.get("q"),
        "opts": q.get("opts"),
        "ans": q.get("ans"),
        "why": q.get("why"),
    } for q in questions]
    return json.dumps(slim, ensure_ascii=False)


def _fact_warn(note: str, source: str = "deepseek-unavailable") -> dict:
    """API/parse failure. Upload is path se nahi rukta."""
    return {
        "ok": True, "score": 100, "source": source, "warn": True,
        "items": [], "bad_ids": [], "notes": [f"WARN: {note}"],
    }


def fact_check(questions, complete) -> dict:
    """complete(system, user) -> model text.

    Confident disagreement blocks (ok False, score 0). API/key/parse
    problems warn and leave ok True so upload continues.
    """
    bad = []
    for q in questions:
        issues = structural_issues(q)
        if issues:
            bad.append({"id": q.get("id"), "issues": issues})
    if bad:
        return {
            "ok": False, "score": 0, "source": "structural", "warn": False,
            "items": bad, "bad_ids": [b["id"] for b in bad],
            "notes": ["exactly one unique correct option required"],
        }
    try:
        raw = complete(FACT_SYSTEM, fact_payload(questions))
    except FactCheckError as e:
        return _fact_warn(str(e))
    try:
        data = _parse_json_blob(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        return _fact_warn("model reply was not JSON")
    source = getattr(complete, "quality_source", "deepseek")
    by_id = {str(it.get("id")): it for it in (data.get("items") or []) if isinstance(it, dict)}
    items = []
    bad_ids = []
    notes = []
    warned = False
    for q in questions:
        it = by_id.get(str(q.get("id")))
        if not it:
            warned = True
            notes.append(f"WARN: {q.get('id')}: model skipped this question — not blocking")
            items.append({"id": q.get("id"), "ok": True, "warn": True})
            continue
        try:
            choice = int(it.get("choice"))
        except (TypeError, ValueError):
            choice = -1
        if choice not in range(4):
            warned = True
            notes.append(f"WARN: {q.get('id')}: model choice unreadable — not blocking")
            items.append({"id": q.get("id"), "ok": True, "warn": True, "choice": choice})
            continue
        ambiguous = bool(it.get("ambiguous"))
        why_ok = bool(it.get("explanation_ok"))
        ok = choice == q.get("ans") and not ambiguous and why_ok
        if not ok:
            bad_ids.append(q.get("id"))
            if choice != q.get("ans"):
                notes.append(
                    f"{q.get('id')}: stored {q.get('ans')} but model chose {choice}"
                )
            if ambiguous:
                notes.append(f"{q.get('id')}: more than one option looks correct")
            if not why_ok:
                notes.append(f"{q.get('id')}: explanation disagrees")
        items.append({
            "id": q.get("id"), "ok": ok, "choice": choice,
            "ambiguous": ambiguous, "explanation_ok": why_ok,
            "note": str(it.get("note") or "")[:180],
        })
    if bad_ids:
        return {
            "ok": False, "score": 0, "source": source, "warn": False,
            "items": items, "bad_ids": bad_ids, "notes": notes,
        }
    return {
        "ok": True, "score": 100, "source": source, "warn": warned,
        "items": items, "bad_ids": [], "notes": notes,
    }


def agreeing_complete(system, user) -> str:
    """Offline stand-in: stored answer se sehmat. Production upload is path nahi hai."""
    questions = json.loads(user)
    items = [{
        "id": q.get("id"), "choice": q.get("ans"),
        "ambiguous": False, "explanation_ok": True, "note": "offline",
    } for q in questions]
    return json.dumps({"items": items}, ensure_ascii=False)


agreeing_complete.quality_source = "offline-mock"


def deepseek_complete(system, user) -> str:
    """OpenAI-compatible DeepSeek chat. Secret name: DEEPSEEK_API_KEY.

    Key kabhi print / exception message mein nahi jaati.
    """
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise FactCheckError("DEEPSEEK_API_KEY missing")
    try:
        import requests
    except ImportError as e:
        raise FactCheckError("requests not installed") from e
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
    base = (os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
    try:
        resp = requests.post(
            base + "/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=90,
        )
    except requests.RequestException as e:
        raise FactCheckError(f"DeepSeek network error: {type(e).__name__}") from None
    if resp.status_code != 200:
        raise FactCheckError(f"DeepSeek HTTP {resp.status_code}")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise FactCheckError("DeepSeek response had no message content")
    if not (content or "").strip():
        raise FactCheckError("DeepSeek returned empty content")
    return content


deepseek_complete.quality_source = "deepseek"


def recent_hooks(path=None, limit=8) -> list[str]:
    path = path or C.QUALITY_HISTORY
    if not path.exists():
        return []
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("hook"):
            lines.append(rec["hook"])
    return lines


def compose(questions, hook, voice, trends, fact, duration, probe, recent=()) -> dict:
    q0 = questions[0] if questions else None
    h, hn = score_hook(hook, voice, recent=recent, question=q0)
    t, tn = score_trend(questions, trends)
    p, pn = score_pacing(duration) if duration is not None else (None, ["pacing not scored yet"])
    v, vn = score_visual(probe, questions) if probe is not None else (None, ["visual not scored yet"])
    scores = {
        "hook": h,
        "trend": t,
        "fact": fact.get("score", 0),
        "visual": v,
        "pacing": p,
    }
    notes = {
        "hook": hn, "trend": tn, "fact": fact.get("notes") or [],
        "visual": vn, "pacing": pn,
    }
    failures = []
    if h < THRESHOLDS["hook"]:
        failures.append("hook")
    if t < THRESHOLDS["trend"]:
        failures.append("trend")
    if not fact.get("ok"):
        failures.append("fact")
    if v is not None and v < THRESHOLDS["visual"]:
        failures.append("visual")
    if p is not None and p < THRESHOLDS["pacing"]:
        failures.append("pacing")
    bad_ids = list(fact.get("bad_ids") or [])
    if "trend" in failures:
        bad_ids = list({*bad_ids, *[q.get("id") for q in questions]})
    passed = not failures and v is not None and p is not None
    reason = ""
    if failures:
        reason = "below threshold: " + ", ".join(failures)
    return {
        "pass": passed,
        "pass_content": not any(f in failures for f in ("hook", "trend", "fact")),
        "scores": scores,
        "thresholds": dict(THRESHOLDS),
        "notes": notes,
        "fact": {k: fact[k] for k in ("ok", "source", "items", "bad_ids", "warn") if k in fact},
        "bad_ids": bad_ids,
        "failures": failures,
        "reason": reason,
        "hook": hook,
        "question_ids": [q.get("id") for q in questions],
        "duration_sec": None if duration is None else round(float(duration), 2),
    }


def precheck(questions, hook, voice, trends, complete, recent=()) -> dict:
    fact = fact_check(questions, complete)
    return compose(questions, hook, voice, trends, fact, duration=None, probe=None, recent=recent)


def finalize(pre: dict, questions, duration, probe) -> dict:
    """Content scores reuse karo; visual + pacing yahin judte hain."""
    fact = {
        "ok": pre["scores"]["fact"] == 100 and "fact" not in pre["failures"],
        "score": pre["scores"]["fact"],
        "source": (pre.get("fact") or {}).get("source"),
        "items": (pre.get("fact") or {}).get("items"),
        "bad_ids": (pre.get("fact") or {}).get("bad_ids") or [],
        "notes": pre["notes"]["fact"],
        "warn": bool((pre.get("fact") or {}).get("warn")),
    }
    # precheck failures for hook/trend/fact carry over via scores
    report = compose(
        questions, pre.get("hook"), pre.get("hook"), None if False else _trends_from_score(pre),
        fact, duration, probe, recent=(),
    )
    # hook/trend were already decided; don't rescore trend from None.
    report["scores"]["hook"] = pre["scores"]["hook"]
    report["scores"]["trend"] = pre["scores"]["trend"]
    report["notes"]["hook"] = pre["notes"]["hook"]
    report["notes"]["trend"] = pre["notes"]["trend"]
    failures = []
    if report["scores"]["hook"] < THRESHOLDS["hook"]:
        failures.append("hook")
    if report["scores"]["trend"] < THRESHOLDS["trend"]:
        failures.append("trend")
    if report["scores"]["fact"] < THRESHOLDS["fact"]:
        failures.append("fact")
    if report["scores"]["visual"] < THRESHOLDS["visual"]:
        failures.append("visual")
    if report["scores"]["pacing"] < THRESHOLDS["pacing"]:
        failures.append("pacing")
    report["failures"] = failures
    report["pass"] = not failures
    report["reason"] = ("below threshold: " + ", ".join(failures)) if failures else ""
    report["bad_ids"] = list(pre.get("bad_ids") or [])
    if "pacing" in failures:
        report["bad_ids"] = list({*report["bad_ids"], *[q.get("id") for q in questions]})
    report["duration_sec"] = round(float(duration), 2)
    return report


def _trends_from_score(pre):
    """finalize ko trend dobara na ginana pade — compose phir se score karta hai.

    Hum scores overwrite kar dete hain, isliye yahan None bhejna sirf temporary hai.
    """
    return None


def questions_by_id(ids: list[str]) -> list[dict]:
    import pick
    bank = {q["id"]: q for q in pick.load_bank()}
    missing = [i for i in ids if i not in bank]
    if missing:
        raise SystemExit(f"[quality] unknown question id: {', '.join(missing)}")
    return [bank[i] for i in ids]


def pick_avoiding(n, slot, banned, seed, now=None):
    """pick.py ko edit kiye bina banned ids hata kar chunta hai. dry-run."""
    import pick
    real = pick.load_bank
    banned = set(banned)

    def filtered():
        return [q for q in real() if q.get("id") not in banned]

    pick.load_bank = filtered
    try:
        return pick.pick(n, dry_run=True, seed=seed, slot=slot, now=now)
    finally:
        pick.load_bank = real


def commit_used(questions, now=None):
    """Pick ke format mein history likho. Sirf gate pass ke baad."""
    import pick
    used = pick.load_used()
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    used.setdefault("history", [])
    used["history"] += [{"id": q["id"], "at": stamp} for q in questions]
    pick.USED.write_text(json.dumps(used, ensure_ascii=False, indent=1), encoding="utf-8")


def append_history(record, path=None):
    path = path or C.QUALITY_HISTORY
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def format_summary(record: dict) -> str:
    scores = record.get("scores") or {}
    lines = [
        "### Quiz quality gate",
        "",
        f"- pass: {record.get('pass')}",
        f"- hook: {scores.get('hook')} (min {THRESHOLDS['hook']})",
        f"- visual: {scores.get('visual')} (min {THRESHOLDS['visual']})",
        f"- trend: {scores.get('trend')} (min {THRESHOLDS['trend']})",
        f"- pacing: {scores.get('pacing')} (min {THRESHOLDS['pacing']})",
        f"- fact: {scores.get('fact')} ({(record.get('fact') or {}).get('source')})"
        + (" WARN — upload not blocked" if (record.get("fact") or {}).get("warn") else ""),
        f"- duration_sec: {record.get('duration_sec')}",
        f"- questions: {', '.join(record.get('question_ids') or [])}",
        f"- hook line: {record.get('hook')}",
    ]
    if record.get("reason"):
        lines.append(f"- reason: {record['reason']}")
    for note in (record.get("notes") or {}).get("fact") or []:
        lines.append(f"- fact note: {note}")
    lines.append("")
    return "\n".join(lines)


def write_report(outdir, record):
    path = outdir / "quality.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("\n" + format_summary(record) + "\n")
    return path


def log_report(record):
    scores = record["scores"]
    print(
        "[quality] "
        f"pass={record['pass']} "
        f"hook={scores.get('hook')} visual={scores.get('visual')} "
        f"trend={scores.get('trend')} pacing={scores.get('pacing')} "
        f"fact={scores.get('fact')} "
        f"source={(record.get('fact') or {}).get('source')}"
    )
    for note in (record.get("notes") or {}).get("fact") or []:
        if str(note).startswith("WARN:"):
            print(f"::warning::{note}")
        print(f"[quality] {note}")
    if not record["pass"]:
        print(f"::error::Quality gate failed — upload blocked. {record.get('reason')}")


def stamp(record) -> dict:
    record = dict(record)
    record["at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return record


def check_report_file(path) -> int:
    report = json.loads(path.read_text(encoding="utf-8"))
    log_report(report)
    if not report.get("pass"):
        print("[quality] FAIL — ye video upload nahi hogi. Doosra sawaal try ho chuka hai.")
        return 1
    print("[quality] PASS — upload allowed")
    return 0


def main(argv=None):
    import argparse
    from pathlib import Path
    ap = argparse.ArgumentParser(description="Quality report check (upload se pehle)")
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    path = args.dir / "quality.json"
    if not path.exists():
        print("::error::quality.json missing — gate chala hi nahi, upload blocked")
        return 1
    return check_report_file(path)


if __name__ == "__main__":
    raise SystemExit(main())
