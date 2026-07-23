"""Fetch and cache real stock footage from Pexels, keyed by each shot's
source_asset_query.

Cached under assets/cache/ so re-renders and later videos on similar topics cost
nothing — Pexels is free but rate-limited, and a daily pipeline re-downloading
the same clips is wasteful.

Everything degrades: no key, no network, no match, or a failed download all
return None, and the caller falls back to a plain card. Footage is a nice-to-have
and must never be able to fail a run.
"""
import hashlib, os, re

import requests

from common import ROOT, ok

CACHE = ROOT / "assets" / "cache"
API_VIDEO = "https://api.pexels.com/videos/search"
API_PHOTO = "https://api.pexels.com/v1/search"
TIMEOUT = 45


def _slug(text):
    base = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:48]
    return f"{base}-{hashlib.sha1(str(text).encode()).hexdigest()[:8]}"


def _key():
    return os.environ.get("PEXELS_API_KEY") or None


def _download(url, path):
    try:
        with requests.get(url, stream=True, timeout=TIMEOUT) as r:
            if r.status_code != 200:
                return None
            tmp = path.with_suffix(path.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
            tmp.replace(path)
        return path
    except requests.RequestException:
        return None


def fetch_video(query, min_seconds=4):
    """Best landscape clip for the query, at or just under 1920 wide. Returns a
    cached Path, or None if anything at all goes wrong."""
    key = _key()
    if not key or not query:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f"v-{_slug(query)}.mp4"
    if dest.exists() and dest.stat().st_size > 20000:
        return dest

    try:
        r = requests.get(API_VIDEO, headers={"Authorization": key},
                         params={"query": query, "per_page": 8,
                                 "orientation": "landscape", "size": "medium"},
                         timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        videos = r.json().get("videos") or []
    except (requests.RequestException, ValueError):
        return None

    for v in videos:
        if float(v.get("duration") or 0) < min_seconds:
            continue
        files = [f for f in v.get("video_files", []) if (f.get("width") or 0) <= 1920]
        if not files:
            continue
        best = max(files, key=lambda f: f.get("width") or 0)
        if _download(best["link"], dest):
            return dest
    return None


def fetch_photo(query):
    key = _key()
    if not key or not query:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f"p-{_slug(query)}.jpg"
    if dest.exists() and dest.stat().st_size > 10000:
        return dest
    try:
        r = requests.get(API_PHOTO, headers={"Authorization": key},
                         params={"query": query, "per_page": 5, "orientation": "landscape"},
                         timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        photos = r.json().get("photos") or []
    except (requests.RequestException, ValueError):
        return None
    for p in photos:
        link = (p.get("src") or {}).get("large2x") or (p.get("src") or {}).get("large")
        if link and _download(link, dest):
            return dest
    return None


def backdrop(query):
    """Video if possible, else a photo, else None."""
    return fetch_video(query) or fetch_photo(query)


def warm_cache(shots):
    """Pre-fetch every shot's footage up front so the render loop doesn't stall
    on network calls, and so one slow query doesn't look like a hang."""
    hits = 0
    for i, s in enumerate(shots):
        q = s.get("source_asset_query")
        if not q:
            continue
        path = backdrop(q)
        s["_backdrop"] = str(path) if path else None
        if path:
            hits += 1
        print(f"  [{i+1}/{len(shots)}] {'ok ' if path else 'miss'}  {q[:56]}")
    ok(f"footage: {hits}/{len(shots)} shots have a backdrop")
    return hits
