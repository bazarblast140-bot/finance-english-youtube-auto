"""Publisher — OPT-IN ONLY. Refuses to upload unless the verify verdict is READY.
Always uploads as PRIVATE (or scheduled), never instant-public, on a finance channel.

Needs: pip install google-api-python-client google-auth-oauthlib
and YOUTUBE_* env vars for the FINANCE channel (separate OAuth from your Hindi channel!).
"""
import re
import sys
from common import cfg, read, die, ok, RUN, need

# The script is written with bare headings on their own line ("TITLE", then the
# title underneath). Older drafts used "TITLE: ...". Both must parse, because
# guessing wrong here uploads a video literally called "Finance video".
HEADINGS = ["TITLE", "HOOK", "BODY", "CTA", "DISCLAIMER LINE", "FACT LEDGER"]
_HEADING_RE = re.compile(rf"^({'|'.join(HEADINGS)})\b[^:]*:?\s*(.*)$", re.I)

MAX_TITLE = 100      # YouTube hard limits
MAX_DESC = 5000
MAX_TAGS_CHARS = 460  # real cap is 500 across all tags; leave headroom


def sections(text):
    """Split script.txt into {heading: body}. Anything before the first heading
    is ignored — it is never content we want on the video page."""
    out, current, buf = {}, None, []
    for line in text.splitlines():
        m = _HEADING_RE.match(line.strip())
        if m:
            if current:
                out[current] = "\n".join(buf).strip()
            current = m.group(1).upper()
            buf = [m.group(2)] if m.group(2).strip() else []
        elif current:
            buf.append(line)
    if current:
        out[current] = "\n".join(buf).strip()
    return out


def build_title(sec):
    title = sec.get("TITLE", "").strip().splitlines()
    title = title[0].strip() if title else ""
    if not title:
        die("No TITLE found in run/script.txt. Refusing to upload an unnamed video.")
    if len(title) > MAX_TITLE:
        # cut on a word boundary rather than mid-word
        title = title[:MAX_TITLE].rsplit(" ", 1)[0]
    return title


def build_description(sec, c):
    """Hook first (it is the search snippet), then the disclaimer, then the
    sourced facts. The fact ledger is the channel's credibility — putting it on
    the page means a viewer can check the claims without watching again."""
    parts = []

    hook = sec.get("HOOK", "").strip()
    if hook:
        parts.append(hook)

    disclaimer = sec.get("DISCLAIMER LINE", "").strip()
    parts.append(disclaimer or "This video is for education only and is not financial advice.")

    ledger = sec.get("FACT LEDGER", "").strip()
    if ledger:
        # drop the VERIFIED bookkeeping — that is for the verify stage, not viewers
        lines = []
        for line in ledger.splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"\s*—\s*(VERIFIED|no source required)\b.*$", "", line, flags=re.I)
            lines.append(line)
        if lines:
            parts.append("SOURCES & NOTES\n" + "\n".join(lines))

    tagline = c["channel"].get("tagline", "").strip()
    if tagline:
        parts.append(f"{c['channel']['name']} — {tagline}")

    desc = "\n\n".join(parts)
    return desc[:MAX_DESC]


def build_tags(title, c):
    """Channel tags from config, then distinctive words from the title. Generic
    stopwords would just dilute the set, so they are dropped."""
    stop = {"the", "that", "your", "when", "what", "how", "why", "and", "for",
            "with", "you", "old", "year", "shows", "it", "a", "of", "in", "to"}
    tags = list(c["channel"].get("tags", []))
    for word in re.findall(r"[A-Za-z0-9]{3,}", title):
        w = word.lower()
        if w.isdigit():  # "500" out of "500-Year-Old" is not a search term
            continue
        if w not in stop and w not in {t.lower() for t in tags}:
            tags.append(w)

    kept, total = [], 0
    for t in tags:
        if total + len(t) + 1 > MAX_TAGS_CHARS:
            break
        kept.append(t)
        total += len(t) + 1
    return kept


def set_thumbnail(yt, video_id):
    """Custom thumbnails need a phone-verified channel. If this account is not
    verified the API says 403 — that is a channel setting, not a broken upload,
    so it must not fail the run after the video is already up."""
    thumb = RUN / "thumbnail.jpg"
    if not thumb.exists():
        print("[skip] no run/thumbnail.jpg — set one manually in YouTube Studio")
        return
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    try:
        yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumb))).execute()
        ok("thumbnail set")
    except HttpError as e:
        if e.resp.status == 403:
            print("[skip] YouTube refused the custom thumbnail (channel not verified).\n"
                  "       Verify at https://www.youtube.com/verify, then set it in Studio.")
        else:
            print(f"[skip] thumbnail upload failed ({e.resp.status}). Video is up; set it in Studio.")


def verdict_is_ready():
    if not (RUN / "report.md").exists():
        return False
    return "READY TO PUBLISH" in read("report.md")

def main():
    only_if_ready = "--only-if-ready" in sys.argv
    if only_if_ready and not verdict_is_ready():
        die("Verify verdict is NOT 'READY TO PUBLISH'. Refusing to upload. (This is by design.)")

    c = cfg()
    if not (RUN / "final.mp4").exists():
        die("No final.mp4 to upload.")

    sec = sections(read("script.txt"))
    title = build_title(sec)
    description = build_description(sec, c)
    tags = build_tags(title, c)
    visibility = c["pipeline"]["publish_visibility"]

    print(f"\n  Title      : {title}")
    print(f"  Tags       : {', '.join(tags) or '(none)'}")
    print(f"  Visibility : {visibility}")
    print(f"  Thumbnail  : {'yes' if (RUN / 'thumbnail.jpg').exists() else 'no'}\n")

    # ---- YouTube upload ----
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    creds = Credentials(
        None,
        refresh_token=need("YOUTUBE_REFRESH_TOKEN"),
        client_id=need("YOUTUBE_CLIENT_ID"),
        client_secret=need("YOUTUBE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    yt = build("youtube", "v3", credentials=creds)

    from googleapiclient.http import MediaFileUpload
    body = {
        "snippet": {"title": title, "description": description, "tags": tags,
                    "categoryId": "27"},  # 27 = Education
        "status": {"privacyStatus": visibility,  # 'private' by default
                   "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(RUN / "final.mp4"), chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    # A 23 MB upload on a slow line is minutes of silence otherwise, and silence
    # is indistinguishable from a hang.
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  uploading… {int(status.progress() * 100)}%")

    video_id = resp["id"]
    ok(f"Uploaded as {visibility}: https://youtu.be/{video_id}")
    set_thumbnail(yt, video_id)
    print(f"\nEdit before going public: https://studio.youtube.com/video/{video_id}/edit")

if __name__ == "__main__":
    main()
