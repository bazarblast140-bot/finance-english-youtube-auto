"""Remove videos from an earlier life of this channel.

    python cleanup_videos.py --before 2026-01-01                 # list only
    python cleanup_videos.py --before 2026-01-01 --delete --yes   # permanent
    python cleanup_videos.py --before 2026-01-01 --private --yes  # reversible

--before is required and there is no default: a cleanup script that runs with no
arguments is one stray Enter away from deleting the channel. Videos newer than
the cutoff are never touched, so anything this pipeline uploads is safe.

Deletion cannot be undone. --private hides a video from everyone exactly like a
delete does, but you can put it back; prefer it unless you are certain.

Needs the full youtube scope — run `python youtube_auth.py` if the stored token
is older than that change.
"""
import sys
from datetime import datetime, timezone

from common import need, ok, die


def arg(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def yt_client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(
        None,
        refresh_token=need("YOUTUBE_REFRESH_TOKEN"),
        client_id=need("YOUTUBE_CLIENT_ID"),
        client_secret=need("YOUTUBE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("youtube", "v3", credentials=creds)


def all_uploads(yt):
    ch = yt.channels().list(part="contentDetails,snippet", mine=True).execute()["items"][0]
    playlist = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=playlist,
                                    maxResults=50, pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        token = r.get("nextPageToken")
        if not token:
            break
    vids = []
    for i in range(0, len(ids), 50):
        vids += yt.videos().list(part="snippet,status,statistics",
                                 id=",".join(ids[i:i + 50])).execute()["items"]
    return ch["snippet"]["title"], vids


def main():
    before = arg("--before")
    if not before:
        die("--before YYYY-MM-DD is required. Videos published on or after that "
            "date are left alone. Example: --before 2026-01-01")
    try:
        cutoff = datetime.strptime(before, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        die("--before must look like 2026-01-01")

    do_delete = "--delete" in sys.argv
    do_private = "--private" in sys.argv
    if do_delete and do_private:
        die("Pick one: --delete or --private.")
    confirmed = "--yes" in sys.argv

    yt = yt_client()
    title, vids = all_uploads(yt)

    targets, kept = [], []
    for v in vids:
        published = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
        (targets if published < cutoff else kept).append((published, v))
    targets.sort(key=lambda p: p[0], reverse=True)

    action = "DELETE" if do_delete else ("make PRIVATE" if do_private else "list")
    print(f"\nChannel: {title}")
    print(f"Cutoff : published before {before}  ->  {len(targets)} to {action}, "
          f"{len(kept)} untouched\n")

    for published, v in targets:
        print(f"  {published:%Y-%m-%d}  {v['status']['privacyStatus']:<8} "
              f"views={v['statistics'].get('viewCount', '0'):<6} {v['snippet']['title'][:64]}")
    if kept:
        print("\n  SAFE (newer than cutoff):")
        for published, v in sorted(kept, key=lambda p: p[0], reverse=True):
            print(f"  {published:%Y-%m-%d}  {v['status']['privacyStatus']:<8} "
                  f"{v['snippet']['title'][:64]}")

    if not targets:
        print("\nNothing matches. Done.")
        return
    if not (do_delete or do_private):
        print("\nList only. Add --delete --yes (permanent) or --private --yes (reversible).")
        return
    if not confirmed:
        print(f"\nWould {action} {len(targets)} videos. Add --yes to actually do it.")
        return
    if do_delete:
        print(f"\nDeleting {len(targets)} videos permanently. This cannot be undone.")

    from googleapiclient.errors import HttpError
    done, failed = 0, []
    for published, v in targets:
        vid, name = v["id"], v["snippet"]["title"][:50]
        try:
            if do_delete:
                yt.videos().delete(id=vid).execute()
            else:
                # videos.update replaces the parts you send, so the snippet has
                # to be carried over intact or the title and category are wiped.
                snip = v["snippet"]
                yt.videos().update(part="status,snippet", body={
                    "id": vid,
                    "snippet": {k: snip[k] for k in
                                ("title", "description", "categoryId", "tags")
                                if k in snip},
                    "status": {"privacyStatus": "private",
                               "selfDeclaredMadeForKids": v["status"].get("madeForKids", False)},
                }).execute()
            done += 1
            print(f"  [{done}/{len(targets)}] {'deleted' if do_delete else 'private'}: {name}")
        except HttpError as e:
            failed.append((vid, name, e.resp.status))
            print(f"  [!] failed ({e.resp.status}): {name}")

    ok(f"{done} of {len(targets)} done")
    if failed:
        print("\nFailed:")
        for vid, name, status in failed:
            print(f"  {vid}  {status}  {name}")
        print("If these are 403: re-run `python youtube_auth.py` for the full scope.")


if __name__ == "__main__":
    main()
