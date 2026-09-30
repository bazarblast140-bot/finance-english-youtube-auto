"""Optional competitor + own-channel research for Quiz Pathshala.

    python src/competitor_research.py              # fetch (agar creds hain) + data/competitor_insights.json likho
    python src/competitor_research.py --dry-run    # sirf summary print, kuch mat likho
    python src/competitor_research.py --max-age-hours 20   # insights taaza hain to skip

Kya karta hai (sirf READ-ONLY YouTube Data API calls — upload/edit kuch nahi):
  1. data/research_sources.json ke competitor channels ke recent uploads, aur
     search_keywords (jaise "gk quiz in hindi") ke top Shorts.
  2. Har video ko uske APNE channel ke median se score karta hai (performance
     index) — bada channel sirf bada hone se nahi jeet-ta.
  3. Aggregate pattern nikaalta hai: title me kya chalta hai (sawaal, number,
     challenge, paheli, exam), winning keywords, title length, upload hour IST,
     Short ki duration.
  4. HAMARE channel ke uploads (data/uploads.json ledger) ke views/day slot aur
     subject ke hisaab se — kaunsa slot/subject kaam kar raha hai.
  5. insight_tags() seo.py ko 1-2 relevant tag deta hai (sirf tag_allowlist wale
     shabd; kisi channel ka naam/brand kabhi nahi). Competitor ka title/script
     kabhi copy nahi hota.

Credentials (pehla jo mile; kuch na ho to saaf skip, exit 0):
  YT_DATA_API_KEY                      (GitHub secret; sabse aasaan, 10k units/day)
  YT_CLIENT_ID/SECRET/REFRESH_TOKEN    (upload wala OAuth — readonly scope kaafi hai)
Quota: ~3-6 units/channel + 100 per search keyword (max 3) + 1 per 50 own videos.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCES = DATA / "research_sources.json"
INSIGHTS = DATA / "competitor_insights.json"
LEDGER = DATA / "uploads.json"
IST = timezone(timedelta(hours=5, minutes=30))

STOP = {"the", "a", "of", "in", "to", "and", "for", "is", "on", "with", "shorts", "short", "video",
        "kya", "hai", "ka", "ki", "ke", "se", "me", "को", "का", "की", "के", "है", "में", "से", "और",
        "क्या", "ये", "यह", "तो", "पर", "एक", "हैं", "नहीं", "कौन", "सा", "सी", "वो", "किस"}


def _read(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _write(path, data):
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def cfg():
    r = _read(SOURCES, {})
    return {
        "enabled": bool(r.get("enabled", True)),
        "lookback_days": int(r.get("lookback_days", 30)),
        "max_videos_per_channel": int(r.get("max_videos_per_channel", 25)),
        "channel_ids": [c["channel_id"] for c in r.get("competitors", [])
                        if isinstance(c, dict) and str(c.get("channel_id", "")).startswith("UC")],
        "search_keywords": list(r.get("search_keywords") or [])[: int(r.get("max_search_keywords", 3))],
        "region_code": r.get("region_code", "IN"),
        "relevance_language": r.get("relevance_language", "hi"),
        "include_own_channel": bool(r.get("include_own_channel", True)),
        "tag_allowlist": [t.lower() for t in r.get("tag_allowlist", [])],
    }


def iso_duration_seconds(s):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def title_labels(title):
    t = (title or "").lower()
    labels = set()
    if "?" in t:
        labels.add("question")
    if re.search(r"\d", t):
        labels.add("number")
    if any(w in t for w in ("चैलेंज", "challenge", "जीनियस", "genius", "सिर्फ", "सिर्फ़", "only", "%",
                            "iq", "बताओ", "test")):
        labels.add("challenge")
    if any(w in t for w in ("पहेली", "paheli", "riddle", "बूझो")):
        labels.add("paheli")
    if any(w in t for w in ("ssc", "upsc", "exam", "परीक्षा", "competitive", "railway", "police")):
        labels.add("exam")
    if re.search(r"[\U0001F300-\U0001FAFF]", title or ""):
        labels.add("emoji")
    return labels


def words(title):
    t = re.sub(r"#\S+", " ", (title or "").lower())
    return [w for w in re.findall(r"[\w\u0900-\u097f]+", t) if len(w) > 2 and w not in STOP and not w.isdigit()]


# ------------------------------------------------------------------ API
def get_client():
    try:
        from googleapiclient.discovery import build
    except ImportError:
        return None, "google-api-python-client not installed"
    key = (os.environ.get("YT_DATA_API_KEY") or "").strip()
    if key:
        return build("youtube", "v3", developerKey=key, cache_discovery=False), "api_key"
    if all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        try:
            from google.oauth2.credentials import Credentials
            creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                                client_id=os.environ["YT_CLIENT_ID"],
                                client_secret=os.environ["YT_CLIENT_SECRET"],
                                token_uri="https://oauth2.googleapis.com/token")
            return build("youtube", "v3", credentials=creds, cache_discovery=False), "oauth"
        except Exception as e:  # noqa: BLE001
            return None, f"oauth unavailable ({type(e).__name__})"
    return None, "no YT_DATA_API_KEY and no YouTube OAuth env"


def channel_uploads(yt, channel_id, since, limit):
    ch = yt.channels().list(part="contentDetails,snippet,statistics", id=channel_id).execute().get("items") or []
    if not ch:
        return None, []
    info = {"id": channel_id, "title": ch[0]["snippet"]["title"],
            "subscribers": int(ch[0].get("statistics", {}).get("subscriberCount", 0) or 0)}
    uploads = ch[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while len(ids) < limit:
        resp = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50,
                                       pageToken=token).execute()
        for it in resp.get("items", []):
            pub = it["contentDetails"].get("videoPublishedAt", "")
            if pub and pub < since:
                return info, ids
            ids.append(it["contentDetails"]["videoId"])
            if len(ids) >= limit:
                break
        token = resp.get("nextPageToken")
        if not token:
            break
    return info, ids


def search_ids(yt, q, since, rc):
    resp = yt.search().list(part="id", q=q, type="video", order="viewCount", publishedAfter=since,
                            regionCode=rc["region_code"], relevanceLanguage=rc["relevance_language"],
                            videoDuration="short", maxResults=25).execute()
    return [i["id"]["videoId"] for i in resp.get("items", []) if i.get("id", {}).get("videoId")]


def video_details(yt, ids):
    out = []
    for i in range(0, len(ids), 50):
        resp = yt.videos().list(part="snippet,statistics,contentDetails,status", id=",".join(ids[i:i + 50])).execute()
        for v in resp.get("items", []):
            sn, st = v["snippet"], v.get("statistics", {})
            pub = datetime.strptime(sn["publishedAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age_days = max(0.5, (datetime.now(timezone.utc) - pub).total_seconds() / 86400)
            views = int(st.get("viewCount", 0) or 0)
            out.append({
                "id": v["id"], "channel_id": sn["channelId"], "channel": sn.get("channelTitle", ""),
                "title": sn.get("title", ""), "tags": (sn.get("tags") or [])[:12],
                "published_ist": pub.astimezone(IST).strftime("%Y-%m-%d %H:%M"),
                "hour_ist": pub.astimezone(IST).hour,
                "duration_s": iso_duration_seconds(v.get("contentDetails", {}).get("duration")),
                "views": views, "likes": int(st.get("likeCount", 0) or 0),
                "comments": int(st.get("commentCount", 0) or 0),
                "views_per_day": round(views / age_days, 1),
                "made_for_kids": v.get("status", {}).get("madeForKids"),
            })
    return out


# ------------------------------------------------------------------ analysis
def add_performance_index(videos):
    by_ch = defaultdict(list)
    for v in videos:
        by_ch[v["channel_id"]].append(v["views_per_day"])
    med = {c: max(1.0, statistics.median(x)) for c, x in by_ch.items()}
    for v in videos:
        v["performance_index"] = round(min(5.0, v["views_per_day"] / med[v["channel_id"]]), 2)
    return videos


def analyse(videos):
    if not videos:
        return {}
    videos = sorted(videos, key=lambda v: (v["performance_index"], v["views_per_day"]), reverse=True)
    top = videos[: max(5, len(videos) // 4)]
    rest = videos[len(top):] or videos

    def rate(group, label):
        return sum(1 for v in group if label in title_labels(v["title"])) / max(1, len(group))

    patterns = {}
    for label in ("question", "number", "challenge", "paheli", "exam", "emoji"):
        tr, rr = rate(top, label), rate(rest, label)
        patterns[label] = {"top_share": round(tr, 2), "rest_share": round(rr, 2),
                           "lift": round((tr + 0.05) / (rr + 0.05), 2)}
    top_words = Counter(w for v in top for w in set(words(v["title"])))
    all_words = Counter(w for v in videos for w in set(words(v["title"])))
    keywords = [w for w, n in top_words.most_common(40) if n >= 2 and n / max(1, all_words[w]) >= 0.4][:15]
    tag_counts = Counter(t.lower() for v in top for t in v["tags"])
    hours = Counter(v["hour_ist"] for v in top)
    shorts = sorted(v["duration_s"] for v in top if 0 < v["duration_s"] <= 180)
    return {
        "videos_analysed": len(videos),
        "title_patterns": patterns,
        "winning_keywords": keywords,
        "top_tags": [t for t, _ in tag_counts.most_common(20)],
        "best_upload_hours_ist": [h for h, _ in hours.most_common(4)],
        "top_short_duration_s": {
            "median": int(statistics.median(shorts)) if shorts else None,
            "p25": shorts[len(shorts) // 4] if shorts else None,
            "p75": shorts[(3 * len(shorts)) // 4] if shorts else None,
        },
        "top_title_length_chars": int(statistics.median([len(v["title"]) for v in top])),
        "top_videos": [{k: v[k] for k in ("channel", "title", "views", "views_per_day", "performance_index",
                                          "duration_s", "published_ist")} for v in top[:15]],
    }


def subject_of(title):
    for key, sub in (("World GK", "दुनिया"), ("दुनिया", "दुनिया"), ("Science", "विज्ञान"),
                     ("विज्ञान", "विज्ञान"), ("India GK", "भारत"), ("भारत", "भारत"),
                     ("पहेली", "पहेली"), ("Paheli", "पहेली")):
        if key in (title or "").split("|")[-1]:
            return sub
    return "सामान्य ज्ञान"


def own_performance(yt):
    """Hamare uploads (data/uploads.json) ke views/day — slot aur subject ke hisaab se."""
    ledger = [e for e in _read(LEDGER, []) if isinstance(e, dict) and e.get("video_id")][-300:]
    if not ledger:
        return {}
    vids = {v["id"]: v for v in video_details(yt, [e["video_id"] for e in ledger])}
    by_slot, by_sub = defaultdict(list), defaultdict(list)
    for e in ledger:
        v = vids.get(e["video_id"])
        if not v:
            continue
        by_slot[e.get("slot", "?")].append(v["views_per_day"])
        by_sub[e.get("subject") or subject_of(v["title"])].append(v["views_per_day"])

    def summ(d):
        return {k: {"videos": len(x), "median_views_per_day": round(statistics.median(x), 2)}
                for k, x in sorted(d.items())}
    allv = [v for v in vids.values()]
    return {"videos_found": len(allv),
            "total_views": sum(v["views"] for v in allv),
            "by_slot": summ(by_slot), "by_subject": summ(by_sub),
            "made_for_kids_flags": Counter(str(v.get("made_for_kids")) for v in allv)}


# ------------------------------------------------------------------ seo hook
def insight_tags(max_n=2, max_age_days=10):
    """seo.py ke liye 1-2 extra tag — sirf taaza insights, sirf allowlist shabd."""
    ins = _read(INSIGHTS, {})
    try:
        gen = datetime.fromisoformat(ins["generated_at"])
        if datetime.now(timezone.utc) - gen > timedelta(days=max_age_days):
            return []
    except (KeyError, ValueError, TypeError):
        return []
    allow = cfg()["tag_allowlist"]
    banned = {c.get("title", "").lower() for c in ins.get("channels", [])}
    out = []
    for t in (ins.get("analysis") or {}).get("top_tags", []):
        tl = t.lower().strip()
        if not tl or len(tl) > 40 or tl in banned or any(b and b in tl for b in banned):
            continue
        if any(a in tl for a in allow):
            out.append(tl)
        if len(out) >= max_n:
            break
    return out


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-age-hours", type=float, default=0)
    args = ap.parse_args()
    rc = cfg()
    if not rc["enabled"]:
        print("[research] disabled in data/research_sources.json")
        return 0
    if args.max_age_hours:
        try:
            gen = datetime.fromisoformat(_read(INSIGHTS, {})["generated_at"])
            if datetime.now(timezone.utc) - gen < timedelta(hours=args.max_age_hours):
                print(f"[research] insights {args.max_age_hours}h se taaza — skip")
                return 0
        except (KeyError, ValueError, TypeError):
            pass
    yt, how = get_client()
    if yt is None:
        print(f"[research] skipped: {how}. Enable karne ke liye secret YT_DATA_API_KEY add karo.")
        return 0
    since = (datetime.now(timezone.utc) - timedelta(days=rc["lookback_days"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    from googleapiclient.errors import HttpError
    ids, channels, errors = [], [], []
    for cid in rc["channel_ids"]:
        try:
            info, vids = channel_uploads(yt, cid, since, rc["max_videos_per_channel"])
            if info:
                channels.append(info)
                ids += vids
        except HttpError as e:
            errors.append(f"channel {cid}: HTTP {e.resp.status}")
    for q in rc["search_keywords"]:
        try:
            ids += search_ids(yt, q, since, rc)
        except HttpError as e:
            errors.append(f"search '{q}': HTTP {e.resp.status}")
    own_ids = {e.get("video_id") for e in _read(LEDGER, []) if isinstance(e, dict)}
    ids = [i for i in dict.fromkeys(ids) if i not in own_ids]
    videos = add_performance_index(video_details(yt, ids)) if ids else []
    analysis = analyse(videos)
    own = {}
    if rc["include_own_channel"]:
        try:
            own = own_performance(yt)
        except HttpError as e:
            errors.append(f"own channel: HTTP {e.resp.status}")
    print(f"[research] via {how}: {len(channels)} channels, {len(videos)} competitor videos, "
          f"own={own.get('videos_found', 0)} videos" + (f"; errors: {errors}" if errors else ""))
    if analysis:
        print(f"[research] winning keywords: {analysis['winning_keywords'][:8]}")
        print(f"[research] best hours IST: {analysis['best_upload_hours_ist']}; "
              f"top Short median {analysis['top_short_duration_s']['median']}s")
    if own:
        print(f"[research] own by slot: {json.dumps(own['by_slot'], ensure_ascii=False)}")
    if args.dry_run or not (videos or own):
        return 0
    _write(INSIGHTS, {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "lookback_days": rc["lookback_days"], "via": how, "channels": channels,
                      "search_keywords": rc["search_keywords"], "errors": errors,
                      "analysis": analysis, "own_channel": own,
                      "policy": "Reference only. Learn aggregate patterns; never reuse competitor titles, "
                                "questions, scripts, thumbnails or layouts."})
    print("[research] wrote data/competitor_insights.json")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 -- research optional hai; pipeline kabhi fail na ho
        print(f"[research] skipped after error: {type(e).__name__}: {str(e)[:200]}")
        sys.exit(0)
