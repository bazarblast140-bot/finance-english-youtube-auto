"""Roz ka competitor + trend research — Quiz Pathshala.

    python src/trend_research.py                 # fetch + data/trends.json + weekly report
    python src/trend_research.py --dry-run        # API call hogi, file nahi likhega
    python src/trend_research.py --max-age-hours 20
    python src/trend_research.py --force          # taaza file ho to bhi dubara

Kya karta hai (READ-ONLY):
  1. Last 7 din ke Hindi GK / paheli / current-affairs Shorts (search.list
     viewCount + videos.list stats). Rank: views per day, 6 ghante se kam
     age ko 6 ghante maante hain taaki 10-minute purani video infinity na ho.
  2. Topic score: subject lexicon + title keywords + optional keyless RSS
     (Google Trends, fallback Google News India). RSS fail ho to job chalti hai.
  3. Title / hook pattern (title + description ki pehli line). Timer aur
     visual notes SIRF metadata se — frames API mein nahi hote.
  4. Channel benchmarks + hamare ledger ke recent uploads (videos.list, 1 unit).
  5. Weekly Hinglish report: reports/trends-YYYY-WW.md

Quota (YouTube Data API):
  search.list = 100 units. videos.list / channels.list = 1.
  Typical day: 4 searches + 2 videos.list + channels.list + own videos.list
  ≈ 405 units. Config cap default 800. Code hard cap 1,200 — 1,500 se neeche,
  chahe JSON mein budget 10000 likh do. Max 6 searches.
  quotaExceeded / dailyLimitExceeded par aur call nahi, exit 0. Useful data
  na ho aur purani trends.json ho to use overwrite nahi karte.

Credentials:
  SIRF YT_DATA_API_KEY. Ye alag Google Cloud project ki key honi chahiye
  (10k units/din upload se alag). Key na ho to skip, exit 0.
  OAuth (YT_CLIENT_* / YOUTUBE_*) is job mein KABHI use nahi hota, chahe
  RESEARCH_ALLOW_OAUTH=1 ho. Upload wale 5 video ~8,000 units khaate hain;
  research unka quota share nahi karegi.

Competitor title/script copy nahi hota. Sirf aggregate pattern.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

from competitor_research import get_client, iso_duration_seconds, title_labels
from config import DATA, ROOT

TRENDS_PATH = DATA / "trends.json"
MANIFEST = DATA / "trend_manifest.txt"
REPORTS = ROOT / "reports"
SOURCES = DATA / "research_sources.json"
LEDGER = DATA / "uploads.json"
CHANNEL_PROFILE = ROOT / "channel" / "channel_profile.json"

IST = timezone(timedelta(hours=5, minutes=30))
SEARCH_COST = 100
LIST_COST = 1
DEFAULT_BUDGET = 800
ABSOLUTE_MAX_BUDGET = 1200          # 1,500 se neeche, config galat ho to bhi
MAX_SEARCH_CALLS_CAP = 6
RESERVE_LIST_UNITS = 4
MIN_AGE_HOURS = 6.0
MAX_SHORT_S = 180
STALE_DAYS = 8
TREND_WEIGHT_BONUS = 0.6            # fresh weight = 1 + bonus * score(0..1)
RSS_TOPIC_FRACTION = 0.25

DEFAULT_QUERIES = [
    "gk quiz in hindi",
    "hindi paheli",
    "current affairs quiz hindi",
    "ssc gk quiz hindi",
]
DEFAULT_RSS = [
    "https://trends.google.com/trending/rss?geo=IN",
    "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN",
    "https://news.google.com/rss?hl=hi&gl=IN&ceid=IN:hi",
]

# Bare "gk"/"quiz" subject nahi banate — wo har title pe hain, signal mar jaata.
SUBJECT_LEXICON = {
    "पहेली": ("पहेली", "paheli", "riddle", "बूझो", "बूझिए", "बूझ"),
    "विज्ञान": ("विज्ञान", "science", "अंतरिक्ष", "ग्रह", "isro", "nasa", "चंद्र", "भौतिक", "रसायन"),
    "भारत": ("भारत", "india", "indian", "संविधान", "स्वतंत्रता", "लोकसभा", "संसद"),
    "दुनिया": ("दुनिया", "world", "महाद्वीप", "महासागर"),
    "सामान्य ज्ञान": ("सामान्य ज्ञान", "samanya gyan", "current affairs", "करंट अफेयर्स", "करंट"),
}

KEYWORD_STOP = {
    "quiz", "quizzes", "hindi", "gk", "shorts", "short", "video", "youtube", "the", "and",
    "for", "with", "your", "this", "that", "from", "what", "who", "how", "viral", "trending",
    "subscribe", "like", "questions", "question", "answer", "answers", "general", "knowledge",
    "samanya", "gyan", "best", "top", "new", "vs", "india", "indian", "world",
    "सवाल", "सवालों", "जवाब", "क्या", "कौन", "कौनसा", "कौनसी", "है", "हैं", "में", "की", "के",
    "का", "को", "से", "एक", "यह", "ये", "और", "नहीं", "वो", "वह", "तो", "पर", "भी", "ही",
    "ने", "हो", "जो", "या", "लिए", "वाला", "वाले", "वाली", "देश", "लोग", "नाम", "आज",
    "नया", "नए", "रोज", "रोज़",
}

GK_HINTS = (
    "gk", "quiz", "exam", "ssc", "upsc", "neet", "isro", "nasa", "nobel", "constitution",
    "parliament", "election", "budget", "rbi", "cyclone", "earthquake", "mission",
    "satellite", "award", "olympics", "census", "scheme", "cabinet", "supreme court",
    "current affairs", "संविधान", "चुनाव", "सरकार", "योजना", "मिशन", "पुरस्कार", "विज्ञान",
    "अंतरिक्ष", "इसरो", "बजट", "संसद", "भूकंप", "चक्रवात", "नोबेल", "ओलंपिक", "करंट",
    "पहेली", "क्विज़", "क्विज", "परीक्षा", "रिजर्व", "रिज़र्व",
)
GK_DENY = (
    "trailer", "lyrics", "box office", "bollywood", "बॉलीवुड", "web series", "वेब सीरीज",
    "actress", "actor",
)

LIMITATION = (
    "YouTube Data API se video ke frames nahi dikhte — timer ki animation, "
    "option ka layout, aur answer-reveal graphic infer nahi ho sakta. "
    "Neeche sirf duration, title/description ki pehli line, HD flag, aur thumbnail URL hai."
)
POLICY = (
    "Reference only. Aggregate patterns seekho. Competitor ka title, sawaal, "
    "script, thumbnail ya layout copy mat karna."
)

HOOK_DETECTORS = (
    ("sawaal", lambda b: "?" in b or "क्या" in b or "कौन" in b),
    ("countdown", lambda b: bool(re.search(r"\d+\s*(सेकंड|second)", b, re.I))),
    ("challenge", lambda b: any(w in b.casefold() for w in ("चैलेंज", "challenge", "बताइए", "बताएं"))),
    ("paheli", lambda b: any(w in b.casefold() for w in ("पहेली", "paheli", "बूझ"))),
    ("exam", lambda b: any(w in b.casefold() for w in ("ssc", "upsc", "exam", "परीक्षा"))),
)


class Quota:
    def __init__(self, budget: int):
        self.budget = budget
        self.spent = 0
        self.exhausted = False
        self.reason = ""
        self.api_dead = False

    def allow(self, units: int, what: str) -> bool:
        if self.exhausted or self.api_dead:
            return False
        if self.spent + units > self.budget:
            self.exhausted = True
            self.reason = f"budget {self.budget}: {what} ({units}) ruk gaya"
            return False
        self.spent += units
        return True

    def mark_api_quota(self, what: str):
        self.exhausted = True
        self.api_dead = True
        self.reason = f"YouTube quota exhausted during {what}"

    def as_dict(self, search_calls: int) -> dict:
        return {
            "budget": self.budget,
            "spent": self.spent,
            "exhausted": self.exhausted,
            "reason": self.reason,
            "search_calls": search_calls,
            "search_unit_cost": SEARCH_COST,
            "list_unit_cost": LIST_COST,
            "typical_day_units": 4 * SEARCH_COST + 5,
            "absolute_max_units": ABSOLUTE_MAX_BUDGET,
            "note": (
                "Typical ~405 (4×search.list + videos/channels/own list). "
                "Hard cap 1200, 1500 se neeche. OAuth use nahi hota."
            ),
        }


def _int(value, default, lo=None, hi=None):
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    if lo is not None:
        n = max(lo, n)
    if hi is not None:
        n = min(hi, n)
    return n


def load_trends_cfg(path=None):
    path = Path(path) if path else SOURCES
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        raw = {}
    block = raw.get("trends") if isinstance(raw, dict) else None
    if not isinstance(block, dict):
        block = {}
    queries = [q.strip() for q in (block.get("search_queries") or DEFAULT_QUERIES)
               if isinstance(q, str) and q.strip()]
    rss = [u for u in (block.get("rss_urls") or DEFAULT_RSS)
           if isinstance(u, str) and u.startswith("https://")]
    region = str(block.get("region_code") or "IN")
    if not re.fullmatch(r"[A-Za-z]{2}", region):
        region = "IN"
    return {
        "enabled": bool(block.get("enabled", True)),
        "lookback_days": _int(block.get("lookback_days"), 7, lo=1, hi=14),
        "budget_config": _int(block.get("daily_quota_budget"), DEFAULT_BUDGET, lo=0),
        "max_search_calls": _int(block.get("max_search_calls"), 4, lo=0, hi=MAX_SEARCH_CALLS_CAP),
        "queries": queries,
        "max_results": _int(block.get("max_results_per_search"), 15, lo=1, hi=25),
        "region_code": region.upper(),
        "relevance_language": str(block.get("relevance_language") or "hi"),
        "rss_urls": rss,
        "stale_days": _int(block.get("stale_after_days"), STALE_DAYS, lo=1, hi=30),
    }


def effective_budget(raw: int) -> int:
    return max(0, min(int(raw), ABSOLUTE_MAX_BUDGET))


def plan_search_count(n_queries: int, budget: int, max_calls: int, reserve: int = RESERVE_LIST_UNITS) -> int:
    room = int(budget) - int(reserve)
    if room < SEARCH_COST:
        return 0
    return max(0, min(int(n_queries), int(max_calls), room // SEARCH_COST))


def views_per_day(views, age_hours, min_age_hours=MIN_AGE_HOURS) -> float:
    hours = max(float(min_age_hours), float(age_hours))
    return float(views) / (hours / 24.0)


def rank_videos(videos):
    return sorted(videos, key=lambda v: (-float(v.get("views_per_day") or 0),
                                        -int(v.get("views") or 0),
                                        str(v.get("id") or "")))


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.astimezone(timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_generated_at(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def since_rfc3339(now: datetime, days: int) -> str:
    return (_to_utc(now) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def search_kwargs(query: str, since: str, cfg: dict) -> dict:
    return {
        "part": "id",
        "q": query,
        "type": "video",
        "order": "viewCount",
        "publishedAfter": since,
        "regionCode": cfg["region_code"],
        "relevanceLanguage": cfg["relevance_language"],
        "videoDuration": "short",
        "maxResults": cfg["max_results"],
        "safeSearch": "moderate",
    }


def videos_list_kwargs(ids) -> dict:
    return {
        "part": "snippet,statistics,contentDetails,status",
        "id": ",".join(ids),
        "maxResults": 50,
    }


def is_quota_error(exc: BaseException) -> bool:
    status = getattr(getattr(exc, "resp", None), "status", None)
    if status not in (403, 429):
        return False
    content = getattr(exc, "content", b"") or b""
    if isinstance(content, bytes):
        blob = content.decode("utf-8", "replace")
    else:
        blob = str(content)
    low = blob.lower()
    return "quotaexceeded" in low or "dailylimitexceeded" in low or "ratelimitexceeded" in low


def is_transport_error(exc: BaseException) -> bool:
    if is_quota_error(exc):
        return True
    if type(exc).__name__ in ("URLError", "HTTPError", "HttpError", "TimeoutError"):
        return True
    return isinstance(exc, TimeoutError) or getattr(getattr(exc, "resp", None), "status", None) is not None


def safe_api_error(exc: BaseException) -> str:
    """Status + reason. Exception text mein API key hoti hai — use mat chhapna."""
    status = getattr(getattr(exc, "resp", None), "status", None)
    content = getattr(exc, "content", b"") or b""
    if isinstance(content, bytes):
        text = content.decode("utf-8", "replace")
    else:
        text = str(content)
    reason = ""
    m = re.search(r'"reason"\s*:\s*"([^"]+)"', text)
    if m:
        reason = m.group(1)[:80]
    if status is None and not reason:
        return type(exc).__name__
    return f"HTTP {status} {reason}".strip()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if tag else ""


def _parse_traffic(text: str):
    digits = re.sub(r"[^\d]", "", text or "")
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def parse_rss(xml_bytes_or_str) -> list:
    if isinstance(xml_bytes_or_str, str):
        raw = xml_bytes_or_str.encode("utf-8")
    else:
        raw = xml_bytes_or_str
    root = ElementTree.fromstring(raw)
    items = []
    for item in root.iter():
        if _local(item.tag) != "item":
            continue
        title, traffic = "", None
        for child in list(item):
            name = _local(child.tag)
            if name == "title" and child.text:
                title = child.text.strip()
            elif name.lower() in ("approx_traffic", "approxtraffic") and child.text:
                traffic = _parse_traffic(child.text)
        if title:
            items.append({"title": title, "traffic": traffic})
    return items


def gk_relevant(title: str) -> bool:
    blob = (title or "").casefold()
    if not blob:
        return False
    if any(d in blob for d in GK_DENY):
        return False
    return any(h in blob for h in GK_HINTS)


def fetch_rss_items(urls, fetch_fn, limit=20):
    errors = []
    kept = []
    for url in urls:
        origin = "google_news" if "news.google." in url else "google_trends"
        try:
            body = fetch_fn(url)
        except Exception as e:  # noqa: BLE001 — RSS optional hai
            if not is_transport_error(e):
                errors.append(type(e).__name__)
            else:
                errors.append(safe_api_error(e) if getattr(getattr(e, "resp", None), "status", None) else type(e).__name__)
            continue
        try:
            items = parse_rss(body)
        except (ElementTree.ParseError, TypeError, ValueError):
            errors.append("rss parse fail")
            continue
        for it in items:
            title = (it.get("title") or "").strip()
            if origin == "google_news":
                title = re.sub(r"\s[-–—]\s+\S.{0,50}$", "", title).strip()
            if gk_relevant(title):
                kept.append({"title": title, "traffic": it.get("traffic"), "origin": origin})
        if len(kept) >= 3:
            break
    return kept[:limit], "; ".join(errors)


def fetch_url(url: str, timeout: int = 8) -> bytes:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "QuizPathshalaTrendResearch/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(1_000_000)


def _first_line(text: str, limit: int) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:limit]
    return ""


def parse_video_item(item: dict, now: datetime, not_before: datetime | None = None):
    if not isinstance(item, dict):
        return None
    sn = item.get("snippet") or {}
    st = item.get("statistics") or {}
    cd = item.get("contentDetails") or {}
    vid = item.get("id")
    if isinstance(vid, dict):
        vid = vid.get("videoId")
    published_raw = sn.get("publishedAt")
    if not vid or not published_raw or "viewCount" not in st:
        return None
    if sn.get("liveBroadcastContent") in ("live", "upcoming"):
        return None
    try:
        published = parse_generated_at(published_raw)
        views = int(st.get("viewCount") or 0)
    except (TypeError, ValueError):
        return None
    if not_before is not None and published < _to_utc(not_before):
        return None
    now_utc = _to_utc(now)
    age_h = (now_utc - published).total_seconds() / 3600.0
    thumbs = sn.get("thumbnails") or {}
    thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
    desc = sn.get("description") or ""
    try:
        likes = int(st.get("likeCount") or 0)
    except (TypeError, ValueError):
        likes = 0
    return {
        "id": vid,
        "channel_id": sn.get("channelId") or "",
        "channel": sn.get("channelTitle") or "",
        "title": sn.get("title") or "",
        "published_at": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "views": views,
        "views_per_day": views_per_day(views, age_h),
        "likes": likes,
        "duration_s": iso_duration_seconds(cd.get("duration")),
        "definition": cd.get("definition") or "",
        "thumbnail_url": thumb or "",
        "hook_line": (sn.get("title") or "").strip()[:120],
        "description_first": _first_line(desc, 140),
        "made_for_kids": (item.get("status") or {}).get("madeForKids"),
    }


def _chunks(ids, size):
    for i in range(0, len(ids), size):
        yield ids[i:i + size]


def collect_videos(cfg, now, quota: Quota, search_fn, videos_fn, own_id: str = ""):
    """Search + videos.list. API quota dead ho to details skip. Local cap pe list chal sakti hai."""
    n = plan_search_count(len(cfg["queries"]), quota.budget, cfg["max_search_calls"])
    ids, queries_ran, errors = [], [], []
    not_before = _to_utc(now) - timedelta(days=cfg["lookback_days"] + 1)
    for q in cfg["queries"][:n]:
        if quota.api_dead:
            break
        if not quota.allow(SEARCH_COST, f"search {q}"):
            break
        try:
            found = search_fn(q) or []
        except Exception as e:  # noqa: BLE001
            if is_quota_error(e):
                quota.mark_api_quota("search")
                errors.append(safe_api_error(e))
                break
            if is_transport_error(e):
                errors.append(safe_api_error(e))
                continue
            raise
        queries_ran.append(q)
        ids.extend(found)
    # order preserve, dupes hatao
    uniq = list(dict.fromkeys(i for i in ids if i))
    videos, filtered = [], 0
    if uniq and not quota.api_dead:
        for batch in _chunks(uniq, 50):
            if not quota.allow(LIST_COST, "videos.list"):
                break
            try:
                items = videos_fn(batch) or []
            except Exception as e:  # noqa: BLE001
                if is_quota_error(e):
                    quota.mark_api_quota("videos.list")
                    errors.append(safe_api_error(e))
                    break
                if is_transport_error(e):
                    errors.append(safe_api_error(e))
                    break
                raise
            for item in items:
                v = parse_video_item(item, now, not_before=not_before)
                if not v or not (0 < v["duration_s"] <= MAX_SHORT_S) or (own_id and v["channel_id"] == own_id):
                    filtered += 1
                    continue
                videos.append(v)
    by_id = {}
    for v in videos:
        by_id.setdefault(v["id"], v)
    return list(by_id.values()), queries_ran, errors, filtered


def collect_channels(quota: Quota, channel_ids, channels_fn) -> dict:
    if quota.api_dead or not channel_ids:
        return {}
    if not quota.allow(LIST_COST, "channels.list"):
        return {}
    try:
        items = channels_fn(list(dict.fromkeys(channel_ids))[:25]) or []
    except Exception as e:  # noqa: BLE001
        if is_quota_error(e):
            quota.mark_api_quota("channels.list")
            return {}
        if is_transport_error(e):
            return {}
        raise
    out = {}
    for it in items:
        if not isinstance(it, dict) or not it.get("id"):
            continue
        stats = it.get("statistics") or {}
        try:
            subs = int(stats.get("subscriberCount")) if stats.get("subscriberCount") is not None else None
        except (TypeError, ValueError):
            subs = None
        out[it["id"]] = subs
    return out


def collect_own(quota: Quota, ids, videos_fn, now) -> list:
    if quota.api_dead or not ids:
        return []
    if not quota.allow(LIST_COST, "videos.list own"):
        return []
    try:
        items = videos_fn(list(dict.fromkeys(ids))[:50]) or []
    except Exception as e:  # noqa: BLE001
        if is_quota_error(e):
            quota.mark_api_quota("own videos.list")
            return []
        if is_transport_error(e):
            return []
        raise
    out = []
    for it in items:
        v = parse_video_item(it, now)
        if v:
            out.append(v)
    return out


def make_search_fn(yt, cfg, since: str):
    def search(q):
        resp = yt.search().list(**search_kwargs(q, since, cfg)).execute()
        ids = []
        for it in resp.get("items") or []:
            vid = (it.get("id") or {}).get("videoId")
            if vid:
                ids.append(vid)
        return ids
    return search


def make_videos_fn(yt):
    def videos(ids):
        if not ids:
            return []
        resp = yt.videos().list(**videos_list_kwargs(ids)).execute()
        return resp.get("items") or []
    return videos


def make_channels_fn(yt):
    def channels(ids):
        if not ids:
            return []
        resp = yt.channels().list(part="statistics,snippet", id=",".join(ids), maxResults=50).execute()
        return resp.get("items") or []
    return channels


def _tokens(text: str):
    t = re.sub(r"#\S+", " ", (text or "").casefold())
    out = []
    for w in re.findall(r"[\w\u0900-\u097f]+", t):
        if len(w) < 3 or w in KEYWORD_STOP or w.isdigit() or w in {s.casefold() for s in SUBJECT_LEXICON}:
            continue
        out.append(w)
    return out


def _subject_hits(text: str):
    blob = (text or "").casefold()
    hit = []
    for sub, words in SUBJECT_LEXICON.items():
        if any(w.casefold() in blob for w in words):
            hit.append(sub)
    return hit


def extract_topics(videos, rss_items):
    sub_score = defaultdict(float)
    sub_n = defaultdict(int)
    key_score = defaultdict(float)
    key_n = defaultdict(int)
    for v in videos:
        blob = f"{v.get('title') or ''} {v.get('description_first') or ''}"
        w = float(v.get("views_per_day") or 0)
        for sub in _subject_hits(blob):
            sub_score[sub] += w
            sub_n[sub] += 1
        for tok in set(_tokens(v.get("title") or "")):
            key_score[tok] += w
            key_n[tok] += 1
    topics = []
    for sub, score in sub_score.items():
        if score <= 0:
            continue
        topics.append({
            "topic": sub, "kind": "subject", "score": round(score, 1),
            "sources": ["youtube"], "sample_count": sub_n[sub],
        })
    keyword_rows = [(k, s) for k, s in key_score.items() if key_n[k] >= 2 and s > 0]
    keyword_rows.sort(key=lambda x: x[1], reverse=True)
    max_key = keyword_rows[0][1] if keyword_rows else 0.0
    rss_unit = (RSS_TOPIC_FRACTION * max_key) if max_key else 10.0
    rss_acc = defaultdict(lambda: {"score": 0.0, "sources": set(), "traffic": None, "n": 0})
    for it in rss_items or []:
        title = re.sub(r"\s+", " ", (it.get("title") or "").strip())[:80]
        if len(title) < 3 or not gk_relevant(title):
            continue
        slot = rss_acc[title.casefold()]
        slot["label"] = title
        slot["score"] += rss_unit
        slot["sources"].add(it.get("origin") or "google_trends")
        slot["n"] += 1
        if it.get("traffic"):
            slot["traffic"] = max(slot["traffic"] or 0, int(it["traffic"]))
    for key, score in keyword_rows[:12]:
        topics.append({
            "topic": key, "kind": "keyword", "score": round(score, 1),
            "sources": ["youtube"], "sample_count": key_n[key],
        })
    rss_rows = sorted(rss_acc.values(), key=lambda s: -s["score"])
    for slot in rss_rows[:8]:
        row = {
            "topic": slot["label"], "kind": "keyword", "score": round(slot["score"], 1),
            "sources": sorted(slot["sources"]), "sample_count": slot["n"],
        }
        if slot["traffic"]:
            row["approx_traffic"] = slot["traffic"]
        topics.append(row)
    topics.sort(key=lambda t: (-float(t["score"]), t["topic"]))
    return topics


def merge_topic_history(previous, topics, now: datetime):
    prev = {}
    if isinstance(previous, dict):
        for t in previous.get("topics") or []:
            if isinstance(t, dict):
                prev[(t.get("kind"), t.get("topic"))] = t
    today = _to_utc(now).date()
    day = today.isoformat()
    for t in topics:
        old = prev.get((t.get("kind"), t.get("topic")))
        dates = []
        if old:
            for d in old.get("dates") or []:
                try:
                    if (today - datetime.fromisoformat(d).date()).days <= 21:
                        dates.append(d)
                except (TypeError, ValueError):
                    continue
            t["first_seen"] = old.get("first_seen") or day
        else:
            t["first_seen"] = day
        if day not in dates:
            dates.append(day)
        t["dates"] = dates[-14:]
        t["last_seen"] = day
    return topics


def keyword_in_question(keyword: str, blob: str) -> bool:
    k = (keyword or "").casefold().strip()
    if len(k) < 3:
        return False
    text = (blob or "").casefold()
    if re.search(r"[a-z]", k):
        return re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", text) is not None
    return k in text


def question_trend_score(question: dict, trends) -> float:
    """0..1. Subject aur keyword alag normalize — badi subject velocity chhote keyword ko na duba de.

    Subject match = 0.35 (poora subject ek jaisa). Keyword match = 0.65 tak.
    Dono milen to 1.0. Isse picker subject rotation ke andar specific sawaal
    ko thoda prefer karta hai, poori list ko ek subject mein nahi dhakelta.
    """
    if not isinstance(question, dict) or not isinstance(trends, dict):
        return 0.0
    topics = [t for t in (trends.get("topics") or []) if isinstance(t, dict)]
    if not topics:
        return 0.0

    def rows(kind):
        got = [t for t in topics if t.get("kind") == kind]
        peak = max((float(t.get("score") or 0) for t in got), default=0.0)
        return got, (peak or 1.0)

    subs, sub_max = rows("subject")
    keys, key_max = rows("keyword")
    sub_s = 0.0
    for t in subs:
        if (t.get("topic") or "") == (question.get("sub") or ""):
            sub_s = max(sub_s, float(t.get("score") or 0) / sub_max)
    blob = f"{question.get('q') or ''} {question.get('topic') or ''}"
    key_s = 0.0
    for t in keys:
        if keyword_in_question(t.get("topic") or "", blob):
            key_s = max(key_s, float(t.get("score") or 0) / key_max)
    return min(1.0, 0.35 * sub_s + 0.65 * key_s)


def weighted_shuffle(items, weights, rng):
    """Efraimidis–Spirakis. Zyada weight = aage aane ka zyada chance, guarantee nahi."""
    if len(items) != len(weights):
        raise ValueError("weights length")
    keyed = []
    for i, (item, w) in enumerate(zip(items, weights)):
        w = max(float(w), 1e-9)
        u = min(max(rng.random(), 1e-12), 1.0 - 1e-12)
        keyed.append((u ** (1.0 / w), i, item))
    keyed.sort(key=lambda row: (row[0], -row[1]), reverse=True)
    return [item for _, _, item in keyed]


def title_pattern_table(videos) -> dict:
    if not videos:
        return {}
    cut = max(1, len(videos) // 4)
    top, rest = videos[:cut], videos[cut:] or videos

    def rate(group, label):
        return sum(1 for v in group if label in title_labels(v.get("title") or "")) / max(1, len(group))

    out = {}
    for label in ("question", "number", "challenge", "paheli", "exam", "emoji"):
        tr, rr = rate(top, label), rate(rest, label)
        out[label] = {"top_share": round(tr, 2), "rest_share": round(rr, 2),
                      "lift": round((tr + 0.05) / (rr + 0.05), 2)}
    return out


def hook_patterns(videos) -> list:
    if not videos:
        return []
    out = []
    n = len(videos)
    for name, fn in HOOK_DETECTORS:
        hit = [v for v in videos if fn(f"{v.get('title') or ''}\n{v.get('description_first') or ''}")]
        if not hit:
            continue
        out.append({
            "pattern": name,
            "share": round(len(hit) / n, 2),
            "examples": [(v.get("hook_line") or v.get("title") or "").strip()[:90] for v in hit[:3]],
            "description_openers": [v.get("description_first") or "" for v in hit[:3] if v.get("description_first")],
            "note": "Title aur description ki pehli line. Frame ke asli pehle 2 second API se nahi dikhte.",
        })
    out.sort(key=lambda r: r["share"], reverse=True)
    return out


def _pct(sorted_vals, p):
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, max(0, int(round((len(sorted_vals) - 1) * p))))
    return sorted_vals[i]


def timer_and_visual(videos) -> tuple:
    durs = sorted(v["duration_s"] for v in videos if 0 < int(v.get("duration_s") or 0) <= MAX_SHORT_S)

    def share(pat):
        if not videos:
            return 0.0
        n = 0
        for v in videos:
            blob = f"{v.get('title') or ''} {v.get('description_first') or ''}"
            if re.search(pat, blob, re.I):
                n += 1
        return round(n / len(videos), 2)

    seconds = []
    for v in videos:
        blob = f"{v.get('title') or ''} {v.get('description_first') or ''}"
        for m in re.findall(r"(\d+)\s*(?:सेकंड|seconds?|sec)\b", blob, re.I):
            seconds.append(int(m))
    med = int(statistics.median(durs)) if durs else None
    styles = []
    if med is not None:
        styles.append("short_under_30s" if med <= 30 else "mid_30_to_60s" if med <= 60 else "over_60s")
    timer_share = share(r"सेकंड|second|timer|टाइमर|टिक")
    styles.append("timer_mentioned_in_text" if timer_share >= 0.2 else "timer_not_in_metadata")
    answer_share = share(r"जवाब|answer|सही विकल्प")
    if answer_share >= 0.2:
        styles.append("answer_word_in_text")
    thumbs = []
    for v in videos[:5]:
        if v.get("thumbnail_url"):
            thumbs.append({"video_id": v["id"], "url": v["thumbnail_url"]})
    defined = [v for v in videos if v.get("definition")]
    hd_share = round(sum(1 for v in defined if v["definition"] == "hd") / len(defined), 2) if defined else None
    title_format = {
        "question_mark_share": round(sum(1 for v in videos if "?" in (v.get("title") or "")) / max(1, len(videos)), 2) if videos else 0,
        "median_chars": int(statistics.median([len(v.get("title") or "") for v in videos])) if videos else None,
    }
    timer = {
        "limitation": LIMITATION,
        "duration_s": {
            "count": len(durs),
            "median": med,
            "p25": _pct(durs, 0.25),
            "p75": _pct(durs, 0.75),
        },
        "timer_mention_share": timer_share,
        "answer_cue_share": answer_share,
        "seconds_mentioned": sorted(set(seconds))[:8],
        "inferred_styles": styles,
    }
    visual = {
        "limitation": LIMITATION,
        "inferable": ["duration_s", "definition hd/sd", "title format", "description first line", "thumbnail url"],
        "not_inferable": ["timer animation", "option layout", "answer-reveal graphic", "on-screen text beyond title"],
        "thumbnail_sample": thumbs,
        "title_format": title_format,
        "hd_share": hd_share,
    }
    return timer, visual


def channel_benchmarks(videos, subscribers=None) -> list:
    subscribers = subscribers or {}
    by = defaultdict(list)
    names = {}
    for v in videos:
        cid = v.get("channel_id") or "?"
        by[cid].append(v)
        names[cid] = v.get("channel") or ""
    rows = []
    for cid, vs in by.items():
        views = [int(v["views"]) for v in vs]
        vpd = [float(v["views_per_day"]) for v in vs]
        rows.append({
            "channel_id": cid,
            "channel": names[cid],
            "videos": len(vs),
            "median_views": round(statistics.median(views), 1),
            "median_views_per_day": round(statistics.median(vpd), 1),
            "top_views": max(views),
            "subscribers": subscribers.get(cid),
        })
    rows.sort(key=lambda r: (-r["median_views_per_day"], r["channel_id"]))
    return rows[:8]


def summarize_own(videos, window_days: int, channel_id: str, skipped: str = "") -> dict:
    out = {"channel_id": channel_id, "window_days": window_days, "videos": len(videos)}
    if skipped:
        out["skipped"] = skipped
    if not videos:
        return out
    out["median_views"] = round(statistics.median([v["views"] for v in videos]), 1)
    out["median_views_per_day"] = round(statistics.median([v["views_per_day"] for v in videos]), 1)
    out["top_views"] = max(v["views"] for v in videos)
    return out


def comparison_block(benchmarks, own) -> dict:
    own_m = (own or {}).get("median_views_per_day")
    comp = [b["median_views_per_day"] for b in benchmarks]
    comp_m = round(statistics.median(comp), 1) if comp else None
    return {
        "our_median_views_per_day": own_m,
        "competitor_sample_median_views_per_day": comp_m,
        "bias_note": (
            "Competitor median un Shorts ka hai jo search mein viewCount se upar aaye — "
            "poore channel ka average nahi. Hamari median recent uploads ki hai. "
            "Seedha 'kitne guna peeche' mat padhna."
        ),
    }


def public_video(v: dict) -> dict:
    return {
        "id": v["id"],
        "channel_id": v.get("channel_id") or "",
        "channel": v.get("channel") or "",
        "title": v.get("title") or "",
        "published_at": v.get("published_at") or "",
        "views": v.get("views") or 0,
        "views_per_day": round(float(v.get("views_per_day") or 0), 1),
        "duration_s": v.get("duration_s") or 0,
        "likes": v.get("likes") or 0,
        "thumbnail_url": v.get("thumbnail_url") or "",
        "hook_line": v.get("hook_line") or "",
        "description_first": v.get("description_first") or "",
    }


def build_document(videos, rss_items, cfg, now, quota: Quota, queries_ran, errors,
                   filtered, own, subscribers, previous, rss_error: str) -> dict:
    ranked = rank_videos(videos)
    topics = merge_topic_history(previous, extract_topics(ranked, rss_items), now)
    timer, visual = timer_and_visual(ranked)
    benches = channel_benchmarks(ranked, subscribers)
    kids_true = sum(1 for v in ranked if v.get("made_for_kids") is True)
    return {
        "generated_at": _to_utc(now).isoformat(timespec="seconds"),
        "lookback_days": cfg["lookback_days"],
        "region_code": cfg["region_code"],
        "relevance_language": cfg["relevance_language"],
        "via": "api_key",
        "quota": quota.as_dict(len(queries_ran)),
        "queries": queries_ran,
        "errors": errors,
        "rss_error": rss_error,
        "rss_items_kept": len(rss_items or []),
        "videos_analysed": len(ranked),
        "filtered_out": filtered,
        "made_for_kids_true": kids_true,
        "topics": topics,
        "title_patterns": title_pattern_table(ranked),
        "hook_patterns": hook_patterns(ranked),
        "timer_and_reveal": timer,
        "visual_notes": visual,
        "channel_benchmarks": benches,
        "own_channel": own,
        "comparison": comparison_block(benches, own),
        "top_videos": [public_video(v) for v in ranked[:12]],
        "policy": POLICY,
    }


def useful(doc: dict) -> bool:
    return bool(doc.get("topics") or doc.get("top_videos"))


def should_replace(doc: dict, previous) -> bool:
    if useful(doc):
        return True
    if doc.get("quota", {}).get("exhausted") and previous:
        return False
    return True


def load_active_trends(now=None, path=None):
    """Picker ke liye. Missing / kharab / stale -> None. Koi exception nahi."""
    path = Path(path) if path else TRENDS_PATH
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
        gen = parse_generated_at(data["generated_at"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        print("[trends] trends.json padha nahi gaya — picker ignore karega")
        return None
    if not isinstance(data, dict):
        return None
    try:
        stale = load_trends_cfg()["stale_days"]
    except Exception:  # noqa: BLE001
        stale = STALE_DAYS
    now_utc = _to_utc(now or datetime.now(timezone.utc))
    age = now_utc - gen
    if age > timedelta(days=stale):
        print(f"[trends] {stale} din se purane — picker ignore karega")
        return None
    return data


def trends_are_fresh(max_age_hours: float, path=None, now=None) -> bool:
    path = Path(path) if path else TRENDS_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        gen = parse_generated_at(data["generated_at"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False
    now_utc = _to_utc(now or datetime.now(timezone.utc))
    return now_utc - gen < timedelta(hours=max_age_hours)


def own_channel_id() -> str:
    try:
        data = json.loads(CHANNEL_PROFILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return ""
    cid = str((data or {}).get("channel_id") or "")
    return cid if cid.startswith("UC") else ""


def parse_uploaded_ist(value):
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M").replace(tzinfo=IST)
    except (TypeError, ValueError):
        return None


def recent_ledger_ids(now: datetime, days: int, limit: int = 50) -> list:
    try:
        rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    if not isinstance(rows, list):
        return []
    now_utc = _to_utc(now)
    out = []
    for row in reversed(rows):
        if not isinstance(row, dict):
            continue
        vid = row.get("video_id")
        ts = parse_uploaded_ist(row.get("uploaded_ist"))
        if not vid or ts is None:
            continue
        if now_utc - ts.astimezone(timezone.utc) <= timedelta(days=days):
            out.append(vid)
        if len(out) >= limit:
            break
    return list(dict.fromkeys(out))


def report_path(now: datetime) -> Path:
    iso = _to_utc(now).isocalendar()
    return REPORTS / f"trends-{iso.year}-{iso.week:02d}.md"


def render_report(doc: dict, now: datetime) -> str:
    iso = _to_utc(now).isocalendar()
    q = doc.get("quota") or {}
    own = doc.get("own_channel") or {}
    comp = doc.get("comparison") or {}
    lines = [
        f"# Trend report — hafte {iso.year}-W{iso.week:02d}",
        "",
        f"Generated: {doc.get('generated_at')} (UTC). Lookback: pichhle {doc.get('lookback_days')} din.",
        "Audience: general / competitive-exam GK. Bacchon wala format copy nahi karna.",
        "",
        "## Quota",
        f"- Is run mein {q.get('spent', 0)} units lage, cap {q.get('budget')} "
        f"(search.list = {SEARCH_COST}, videos.list/channels.list = {LIST_COST}).",
        f"- Search calls: {q.get('search_calls', 0)}. Quota exhausted: {q.get('exhausted')}.",
        f"- {q.get('note', '')}",
        "- Daily job sirf `YT_DATA_API_KEY` se chalti hai. Upload wala OAuth client use nahi hota, "
        "taaki 5 video (~8,000 units) bache rahen. Key alag Google Cloud project ki honi chahiye.",
        "",
        "## Competitors is hafte kya kar rahe hain",
    ]
    topics = doc.get("topics") or []
    if not topics:
        lines.append("- Is baar koi topic score nahi bana (search khaali, ya filter ne sab hata diya).")
    else:
        lines.append("Topic score is run ka hai. Date list batati hai topic pehle bhi dikha tha ya nahi.")
        for t in topics[:8]:
            dates = ", ".join(t.get("dates") or [])
            lines.append(
                f"- {t.get('topic')} ({t.get('kind')}) score {t.get('score')} "
                f"— {t.get('sample_count', 0)} sample — {dates}"
            )
    patterns = doc.get("title_patterns") or {}
    if patterns:
        bits = [f"{k} top {v.get('top_share')}" for k, v in patterns.items()]
        lines.append("- Title patterns (top quartile vs baaki): " + ", ".join(bits) + ".")
    lines += ["", "## Hook (pehli line / pehle 2 second ka proxy)"]
    lines.append("Asli frame ka pehla 2 second API se nahi dikhta. Neeche title aur description ki pehli line hai.")
    hooks = doc.get("hook_patterns") or []
    if not hooks:
        lines.append("- Hook pattern nahi nikla.")
    for h in hooks:
        ex = h.get("examples") or []
        sample = f" Udaharan: {ex[0]}" if ex else ""
        lines.append(f"- {h.get('pattern')}: {int(round(100 * float(h.get('share') or 0)))}% videos.{sample}")
    timer = doc.get("timer_and_reveal") or {}
    dur = (timer.get("duration_s") or {})
    lines += [
        "",
        "## Timer aur answer reveal",
        timer.get("limitation") or LIMITATION,
        f"- Duration median {dur.get('median')}s (p25 {dur.get('p25')}, p75 {dur.get('p75')}, n={dur.get('count')}).",
        f"- Text mein timer/सेकंड ka share: {timer.get('timer_mention_share')}. "
        f"Jawab/answer ka share: {timer.get('answer_cue_share')}.",
        "- Inferred styles: " + ", ".join(timer.get("inferred_styles") or []) + ".",
        "- Hamara format: 8 second ka on-screen timer, jawab aakhir mein. "
        "Ye metadata se ye nahi pata ki competitor timer dikhata bhi hai ya nahi — sirf text mein 'सेकंड' hai ya nahi.",
        "",
        "## Visual notes",
        (doc.get("visual_notes") or {}).get("limitation") or LIMITATION,
    ]
    visual = doc.get("visual_notes") or {}
    tf = visual.get("title_format") or {}
    lines.append(
        f"- Title par sawaal-mark share {tf.get('question_mark_share')}, "
        f"median title {tf.get('median_chars')} akshar, HD share {visual.get('hd_share')}."
    )
    thumbs = visual.get("thumbnail_sample") or []
    if thumbs:
        lines.append(f"- Thumbnail sample (API URL, frame nahi): {thumbs[0].get('url')}")
    kids = doc.get("made_for_kids_true") or 0
    if kids:
        lines.append(
            f"- {kids} result par madeForKids true tha. Unka bachchon wala framing copy mat karna — "
            "QUIZ PATHSHALA general audience hai."
        )
    lines += ["", "## Hamara channel vs ye sample"]
    lines.append(comp.get("bias_note") or "")
    if own.get("skipped"):
        lines.append(f"- Hamare stats is baar nahi mile ({own.get('skipped')}).")
    elif not own.get("videos"):
        lines.append("- Ledger mein is window ke video id nahi mile, ya videos.list khaali aaya.")
    else:
        lines.append(
            f"- Hamari median: {own.get('median_views')} views, "
            f"{own.get('median_views_per_day')} views/day "
            f"({own.get('videos')} videos, {own.get('window_days')} din)."
        )
        lines.append(
            f"- Competitor sample median views/day: {comp.get('competitor_sample_median_views_per_day')}."
        )
    lines += [
        "",
        "## Picker",
        "pick.py in topics ko soft weight deta hai: sirf fresh sawaal, matching topic thoda aage. "
        "Cooldown aur least-recently-used waise ke waise. trends.json gayab, kharab, ya "
        f"{STALE_DAYS} din se purani ho to bias band — purana shuffle.",
        "Naye sawaal auto bank mein nahi jaate. `src/propose_questions.py` "
        "`data/question_candidates.json` mein review ke liye likhta hai. "
        "Wahan se haath se copy karo, verify karke.",
        "",
        "## Policy",
        POLICY,
        "",
    ]
    return "\n".join(lines)


def write_manifest(paths: list):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(("\n".join(paths) + "\n") if paths else "", encoding="utf-8")


def add_manifest_line(rel: str):
    existing = []
    try:
        existing = [ln.strip() for ln in MANIFEST.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        existing = []
    if rel not in existing:
        existing.append(rel)
    write_manifest(existing)


def persist(doc: dict, now: datetime) -> list:
    TRENDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRENDS_PATH.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    path = report_path(now)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(doc, now), encoding="utf-8")
    rels = ["data/trends.json", f"reports/{path.name}"]
    write_manifest(rels)
    return rels


def _read_previous():
    try:
        data = json.loads(TRENDS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _print_summary(doc: dict):
    q = doc["quota"]
    tops = [t["topic"] for t in (doc.get("topics") or [])[:6]]
    print(f"[trends] spent {q['spent']}/{q['budget']} search={q['search_calls']} "
          f"videos={doc.get('videos_analysed')} topics={len(doc.get('topics') or [])} "
          f"exhausted={q['exhausted']}")
    if tops:
        print("[trends] topics: " + ", ".join(tops))
    if q.get("reason"):
        print(f"[trends] quota note: {q['reason']}")
    for err in doc.get("errors") or []:
        print(f"[trends] error: {err}")
    if doc.get("rss_error"):
        print(f"[trends] rss: {doc['rss_error']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Daily Hindi GK Shorts trend research")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--max-age-hours", type=float, default=0)
    args = ap.parse_args(argv)
    cfg = load_trends_cfg()
    if not cfg["enabled"]:
        print("[trends] disabled in data/research_sources.json")
        return 0
    if not args.force and args.max_age_hours and trends_are_fresh(args.max_age_hours):
        print(f"[trends] {args.max_age_hours}h se taaza — API skip")
        return 0
    yt, how = get_client()
    if how == "oauth":
        print("[trends] OAuth mila, use nahi karenge — upload quota bachane ke liye. "
              "Alag project ki YT_DATA_API_KEY lagao.")
        return 0
    if yt is None or how != "api_key":
        print(f"[trends] skipped: {how}. Secret YT_DATA_API_KEY (alag Google Cloud project) add karo.")
        return 0
    budget = effective_budget(cfg["budget_config"])
    if budget < cfg["budget_config"]:
        print(f"[trends] budget {cfg['budget_config']} ko {budget} par kaata (hard cap)")
    quota = Quota(budget)
    now = datetime.now(timezone.utc)
    since = since_rfc3339(now, cfg["lookback_days"])
    own_id = own_channel_id()
    videos, queries_ran, errors, filtered = collect_videos(
        cfg, now, quota, make_search_fn(yt, cfg, since), make_videos_fn(yt), own_id)
    rss_items, rss_error = [], ""
    try:
        rss_items, rss_error = fetch_rss_items(cfg["rss_urls"], fetch_url)
    except Exception as e:  # noqa: BLE001
        rss_error = type(e).__name__
    ranked_ids = [v["channel_id"] for v in videos if v.get("channel_id")]
    subscribers = collect_channels(quota, ranked_ids, make_channels_fn(yt))
    window = cfg["lookback_days"]
    own_ids = recent_ledger_ids(now, window)
    if len(own_ids) < 3:
        own_ids = recent_ledger_ids(now, 30)
        window = 30
    skipped = ""
    if quota.api_dead:
        skipped = "quota"
        own_videos = []
    else:
        own_videos = collect_own(quota, own_ids, make_videos_fn(yt), now)
        if not own_ids:
            skipped = "no ledger ids in window"
    own = summarize_own(own_videos, window, own_id, skipped=skipped)
    previous = _read_previous()
    doc = build_document(videos, rss_items, cfg, now, quota, queries_ran, errors,
                         filtered, own, subscribers, previous, rss_error)
    _print_summary(doc)
    if args.dry_run:
        print("[trends] dry-run — file nahi likhi")
        return 0
    if not should_replace(doc, previous):
        print("[trends] quota exhausted, useful data nahi — purani trends.json rakhi")
        return 0
    rels = persist(doc, now)
    print("[trends] wrote " + ", ".join(rels))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[trends] error: {type(e).__name__}: {str(e)[:200]}")
        sys.exit(1)
