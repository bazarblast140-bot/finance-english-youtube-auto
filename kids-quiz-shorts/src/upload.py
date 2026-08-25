"""YouTube pe upload. Refresh-token auth — GitHub Actions me interactive login
possible nahi hai, isliye token pehle ek baar local machine pe banao
(neeche `--auth` wala mode).

Usage:
    python src/upload.py --auth                      # ek baar, laptop pe
    python src/upload.py --dir out/20260825_morning  # CI me
    python src/upload.py --dir ... --privacy private # test upload

Quota warning: ek upload ~1600 quota units kharch karta hai. Default daily
quota 10,000 hai = din me ~6 upload. Tumhein 2/din chahiye, so headroom hai —
par agar script retry loop me phans gayi to quota ek hi din me khatam.
Isliye retry max 2 rakha hai.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]


def _creds():
    from google.oauth2.credentials import Credentials
    cid = os.environ["YT_CLIENT_ID"]
    csec = os.environ["YT_CLIENT_SECRET"]
    rtok = os.environ["YT_REFRESH_TOKEN"]
    return Credentials(
        None, refresh_token=rtok, client_id=cid, client_secret=csec,
        token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES,
    )


def do_auth():
    """Local machine pe chalao. client_secret.json Google Cloud Console se
    download karo (OAuth client type: Desktop app)."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)
    print("\n=== Ye teen values GitHub repo Secrets me daalo ===")
    print("YT_CLIENT_ID     =", creds.client_id)
    print("YT_CLIENT_SECRET =", creds.client_secret)
    print("YT_REFRESH_TOKEN =", creds.refresh_token)


def upload(meta_path: Path, privacy="public", publish_at=None):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    video = Path(meta["video_file"])
    if not video.exists():
        video = meta_path.parent / video.name
    assert video.exists(), f"MP4 nahi mila: {video}"

    status = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": bool(meta.get("made_for_kids", True)),
    }
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at       # RFC3339, e.g. 2026-08-26T02:00:00Z

    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": meta.get("categoryId", "27"),
            "defaultLanguage": "hi",
            "defaultAudioLanguage": "hi",
        },
        "status": status,
    }

    yt = build("youtube", "v3", credentials=_creds(), cache_discovery=False)
    media = MediaFileUpload(str(video), chunksize=4 * 1024 * 1024,
                            resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    resp, tries = None, 0
    while resp is None:
        try:
            prog, resp = req.next_chunk()
            if prog:
                print(f"[upload] {int(prog.progress() * 100)}%")
        except HttpError as e:
            tries += 1
            if tries > 2 or e.resp.status not in (500, 502, 503, 504):
                raise
            print(f"[upload] retry {tries} after {e.resp.status}")
            time.sleep(5 * tries)

    vid = resp["id"]
    print(f"[upload] done -> https://youtube.com/shorts/{vid}")

    pinned = meta.get("pinned_comment")
    if pinned and not meta.get("made_for_kids"):
        try:
            yt.commentThreads().insert(part="snippet", body={"snippet": {
                "videoId": vid,
                "topLevelComment": {"snippet": {"textOriginal": pinned}},
            }}).execute()
            print("[upload] pinned comment posted (pin manually — API pin nahi karta)")
        except Exception as e:
            print(f"[upload] comment skip: {e}")

    meta["youtube_id"] = vid
    meta["youtube_url"] = f"https://youtube.com/shorts/{vid}"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return vid


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--auth", action="store_true")
    ap.add_argument("--dir", type=Path)
    ap.add_argument("--privacy", default="public",
                    choices=["public", "private", "unlisted"])
    ap.add_argument("--publish-at", default=None)
    a = ap.parse_args()
    if a.auth:
        do_auth()
    elif a.dir:
        upload(a.dir / "metadata.json", a.privacy, a.publish_at)
    else:
        ap.error("--auth ya --dir me se ek do")
        sys.exit(2)
