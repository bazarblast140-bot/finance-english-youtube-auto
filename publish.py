"""Publisher — OPT-IN ONLY. Refuses to upload unless the verify verdict is READY.
Always uploads as PRIVATE (or scheduled), never instant-public, on a finance channel.

Needs: pip install google-api-python-client google-auth-oauthlib
and YOUTUBE_* env vars for the FINANCE channel (separate OAuth from your Hindi channel!).
"""
import sys
from common import cfg, read, die, ok, RUN, need

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

    # title = first line of script TITLE:, fallback generic
    title = "Finance video"
    for line in read("script.txt").splitlines():
        if line.strip().upper().startswith("TITLE:"):
            title = line.split(":", 1)[1].strip()
            break

    from googleapiclient.http import MediaFileUpload
    body = {
        "snippet": {"title": title, "description": "Educational finance content. Not financial advice.",
                    "categoryId": "27"},  # 27 = Education
        "status": {"privacyStatus": c["pipeline"]["publish_visibility"],  # 'private' by default
                   "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(RUN / "final.mp4"), chunksize=-1, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = req.execute()
    ok(f"Uploaded as {c['pipeline']['publish_visibility']}: https://youtu.be/{resp['id']}")

if __name__ == "__main__":
    main()
