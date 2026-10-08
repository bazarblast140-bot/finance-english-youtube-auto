"""YouTube pe upload. Refresh-token auth — GitHub Actions me interactive login
possible nahi hai, isliye token pehle ek baar local machine pe banao
(neeche `--auth` wala mode).

Usage:
    python src/upload.py --auth --set-github-secret  # ek baar, laptop pe (force-ssl ke saath)
    python src/upload.py --post-pending-comments     # CI: public ho chuki videos par pending comment
    python src/upload.py --dir out/20260825_morning  # CI me
    python src/upload.py --dir ... --privacy private # test upload

Quota warning: ek upload ~1600 quota units kharch karta hai. Default daily
quota 10,000 hai = din me ~6 upload. Tumhein 5/din chahiye, so headroom hai —
par agar script retry loop me phans gayi to quota ek hi din me khatam.
Isliye retry max 2 rakha hai.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as C

IST = timezone(timedelta(hours=5, minutes=30))


def resolve_publish_at(slot: str):
    """Slot ke exact IST time ka RFC3339 (UTC) lautata hai.

    Kyun: GitHub ka cron on-time nahi hai — runner load pe runs 10-20 ghante
    late tak chal jaate hain. Isliye hum cron ko target se ~20h PEHLE chalate
    hain aur video ko 'private + publishAt' ke saath upload karte hain.
    Uske baad publish YouTube ke haath me hai — video hamesha exact clock
    time pe live hoti hai.

    Agar run itna late chala ki AAJ ka target nikal gaya, to KAL usi time
    pe schedule karte hain (pehle turant-public kar dete the jo galat time
    pe live ho jaata tha).
    """
    label = C.SLOTS.get(slot, "")            # e.g. "20:30 IST"
    if not label:
        print(f"[upload] WARN: unknown slot {slot!r} — publishAt skip, turant privacy use hogi")
        return None
    try:
        hh, mm = label.split()[0].split(":")
        h, m = int(hh), int(mm)
    except Exception as e:
        print(f"[upload] WARN: slot time parse fail ({label!r}): {e}")
        return None
    now_ist = datetime.now(timezone.utc).astimezone(IST)
    target = now_ist.replace(hour=h, minute=m, second=0, microsecond=0)
    # 5 min buffer — build+upload ke beech thoda time lag sakta hai
    if target <= now_ist + timedelta(minutes=5):
        target = target + timedelta(days=1)
        print(
            f"[upload] {slot}: aaj ka time ({label}) nikal chuka "
            f"(ab {now_ist.strftime('%H:%M IST')}) — "
            f"KAL {label} pe schedule "
            f"({target.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})"
        )
    else:
        print(
            f"[upload] {slot}: YouTube {label} par khud public karega "
            f"({target.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}) "
            f"— abhi {now_ist.strftime('%H:%M IST')}"
        )
    return target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Auth ke waqt ye scopes maange jaate hain (python src/upload.py --auth).
# Refresh ke waqt scope param NAHI bhejte (_creds) — Google jo granted hai
# wahi deta hai, isliye yahan naya scope jodne se purana token toot-ta nahi.
#
# force-ssl KYUN: commentThreads.insert ke docs me SIRF
# https://www.googleapis.com/auth/youtube.force-ssl likha hai
# (https://developers.google.com/youtube/v3/docs/commentThreads/insert).
# Purana comment "full youtube scope se bhi chal jaata hai" galat tha — har
# upload ke baad log me aata tha:
#   commentThreads 403 insufficientPermissions
#   "Request had insufficient authentication scopes"
# Yaani pinned comment AAJ TAK ek bhi video par nahi gaya. Fix: naya token
# is list ke saath banao (README: "Pinned comment ke liye token").
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
FORCE_SSL = "https://www.googleapis.com/auth/youtube.force-ssl"
LEDGER = C.DATA / "uploads.json"


def _creds():
    """Refresh-token se credentials. Token mara hua ho (invalid_grant) to saaf
    message ke saath fail — pehle raw traceback aata tha."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google.auth.exceptions import RefreshError
    cid = os.environ["YT_CLIENT_ID"]
    csec = os.environ["YT_CLIENT_SECRET"]
    rtok = os.environ["YT_REFRESH_TOKEN"]
    # scopes JAAN-BOOJH KE nahi bhej rahe. Refresh ke waqt scope param bhejne se
    # Google use granted set se match karta hai; zara sa farq bhi ho to
    # invalid_scope aata hai. Bina param ke wo jo granted hai wahi de deta hai.
    creds = Credentials(
        None, refresh_token=rtok, client_id=cid, client_secret=csec,
        token_uri="https://oauth2.googleapis.com/token",
    )
    try:
        creds.refresh(Request())
    except RefreshError as e:
        msg = str(e)
        if "invalid_grant" in msg:
            raise SystemExit(
                "[upload] YouTube token mar chuka hai (invalid_grant: expired/revoked). "
                "Laptop par `python src/upload.py --auth --set-github-secret` chalao. "
                "Agar har 7 din me marta hai to Google Cloud Console > OAuth consent "
                "screen ko 'Testing' se 'In production' karo.") from None
        raise
    return creds


def granted_scopes(creds):
    """Access token ke asli granted scopes (tokeninfo endpoint, read-only).
    Fail ho to None — tab comment try karke dekh lenge."""
    try:
        import requests
        r = requests.get("https://oauth2.googleapis.com/tokeninfo",
                         params={"access_token": creds.token}, timeout=15)
        if r.ok:
            return set(r.json().get("scope", "").split())
    except Exception:
        pass
    return None


GITHUB_REPO = "bazarblast140-bot/finance-english-youtube-auto"
COMMENT_MAX_ATTEMPTS = 3      # pending comment itni baar fail ho to chhod do (50 units/try)


def set_github_secret_value(secret_name, value, repo=GITHUB_REPO):
    """Secret value stdin se `gh` ko do — `--body` ke BINA.

    `gh secret set NAME --body -` value ko literal "-" bana deta hai (gh me
    --body ka "-" stdin nahi hota), aur us din se har upload invalid_grant se
    fail hota. Bina --body ke gh value stdin se padhta hai. Value kabhi
    print/log nahi hoti, aur repo hamesha explicit (-R) hai taaki galti se
    kisi aur repo (cwd) me na chali jaaye."""
    import subprocess
    subprocess.run(["gh", "secret", "set", secret_name, "-R", repo],
                   input=value.encode(), check=True,
                   stdout=subprocess.DEVNULL)


def do_auth(client_secret="client_secret.json", set_github_secret=False,
            secret_name="YOUTUBE_REFRESH_TOKEN"):
    """Local machine pe chalao. client_secret.json Google Cloud Console se
    download karo (OAuth client type: Desktop app) — YOUTUBE_CLIENT_ID/SECRET
    wala hi client, warna token us client ke saath nahi chalega.

    Token terminal me PRINT nahi hota (screen share / shell history me leak
    ho jaata tha). Ya to seedha GitHub secret me jaata hai (--set-github-secret,
    `gh` login chahiye) ya .yt_refresh_token file me (gitignored, chmod 600)."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
    # prompt=consent + offline: har baar naya refresh token milta hai, aur
    # consent screen par force-ssl (comments) wala checkbox bhi dikhta hai.
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    if not creds.refresh_token:
        raise SystemExit("Google ne refresh token nahi diya. https://myaccount.google.com/permissions "
                         "se app ka access hatao aur dobara chalao.")
    got = set(creds.scopes or [])
    missing = [x for x in SCOPES if got and x not in got]
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    items = yt.channels().list(part="snippet", mine=True).execute().get("items") or []
    title = items[0]["snippet"]["title"] if items else "(koi channel nahi!)"
    print(f"\nAuthorised channel: {title}  (id {items[0]['id'] if items else '-'})")
    if missing:
        print("WARNING: ye scopes grant NAHI hue (consent screen par checkbox chhoot gaya?):")
        for m in missing:
            print("   -", m)
    if input(f"Kya '{title}' hi QUIZ PATHSHALA hai? [y/N] ").strip().lower() != "y":
        raise SystemExit("Kuch nahi likha. Dobara chalao aur sahi channel chuno.")
    if set_github_secret:
        set_github_secret_value(secret_name, creds.refresh_token)
        print(f"GitHub secret {secret_name} ({GITHUB_REPO}) update ho gaya (value print nahi ki).")
    else:
        path = Path(".yt_refresh_token")
        path.write_text(creds.refresh_token, encoding="utf-8")
        os.chmod(path, 0o600)
        print(f"Refresh token {path.resolve()} me likha (gitignored). GitHub secret "
              f"{secret_name} me paste karo, phir ye file mita do.")
    print("YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET badalne ki zaroorat nahi agar wahi client use kiya.")


def post_comment(yt, video_id, channel_id, text):
    """Top-level comment (API pin nahi kar sakta — Studio me pin karna padta hai).
    Docs ke hisaab se snippet.channelId bhi zaroori hai; pehle ye nahi bhejte the."""
    body = {"snippet": {"videoId": video_id,
                        "topLevelComment": {"snippet": {"textOriginal": text}}}}
    if channel_id:
        body["snippet"]["channelId"] = channel_id
    return yt.commentThreads().insert(part="snippet", body=body).execute()


def _ledger():
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save_ledger(rows):
    LEDGER.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def _public_video_ids(yt, ids):
    """videos.list (1 unit). None = unknown, caller may try the comment anyway.

    A MagicMock or any non-dict response means 'unknown' so unit tests that
    stub the client keep the old behaviour. Still-private videos are not
    counted as a failed attempt — YouTube 403s comments until publishAt.
    """
    try:
        resp = yt.videos().list(part="status", id=",".join(ids)).execute()
    except Exception:
        return None
    if not isinstance(resp, dict):
        return None
    public = set()
    for video in resp.get("items") or []:
        if not isinstance(video, dict):
            continue
        status = video.get("status") or {}
        if status.get("privacyStatus") == "public" and video.get("id"):
            public.add(video["id"])
    return public


def _already_commented(yt, video_id, channel_id, text):
    """commentThreads.list (1 unit): kya hamara ye comment video par pehle se hai?

    KYUN: 07-Oct-2026 run 37655462843 ne yniJ9SyT9GM par comment daal diya,
    par ledger push 5/5 fail hua (comment_posted save nahi hua). Agle run
    (37680360845) ne wahi comment DOBARA daal diya — video par do ek jaise
    channel comments. Ab insert se pehle check: same channel + same text
    mile to sirf ledger update, naya comment nahi (50 units bhi bachte hain).

    True/False; None = pata nahi (error / MagicMock) — tab purana behaviour.
    """
    try:
        resp = yt.commentThreads().list(
            part="snippet", videoId=video_id, maxResults=50,
            textFormat="plainText", order="time",
        ).execute()
    except Exception:
        return None
    if not isinstance(resp, dict):
        return None
    want = " ".join(str(text or "").split())
    for item in resp.get("items") or []:
        top = (((item or {}).get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
        author = (top.get("authorChannelId") or {}).get("value")
        if channel_id and author != channel_id:
            continue
        got = " ".join(str(top.get("textOriginal") or top.get("textDisplay") or "").split())
        if got == want:
            return True
    return False


def post_pending_comments(max_n=5):
    """Scheduled (private + publishAt) video par upload ke turant baad comment
    ho sake ya na ho — isliye jo reh gaye, unhe video public hone ke BAAD daalte
    hain. Catch-up workflow ye bina naye upload ke chalata hai.

    Pending list = uploads.json rows with pinned_comment and no comment_posted.
    Post hone par comment_posted set hota hai — row pending set se hat jaati
    hai (upload history row rehti hai). 50 quota units/comment, isliye max_n.
    """
    from slot_planner import pending_comment_rows

    rows = _ledger()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    todo = pending_comment_rows(rows, now, COMMENT_MAX_ATTEMPTS)[-max_n:]
    if not todo:
        print("[comments] koi pending comment nahi")
        return 0
    creds = _creds()
    scopes = granted_scopes(creds)
    if scopes is not None and FORCE_SSL not in scopes:
        print("[comments] SKIP: token me youtube.force-ssl scope nahi hai — README "
              "'Pinned comment ke liye token' dekho. (Ye 403 insufficientPermissions ka asli kaaran hai.)")
        return 0
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    public_ids = _public_video_ids(yt, [r["video_id"] for r in todo if r.get("video_id")])
    done = 0
    for r in todo:
        if public_ids is not None and r.get("video_id") not in public_ids:
            print(f"[comments] {r.get('video_id')} abhi public nahi — attempt nahi badhaya")
            continue
        if _already_commented(yt, r["video_id"], r.get("channel_id"), r["pinned_comment"]):
            r["comment_posted"] = now
            print(f"[comments] {r['video_id']} par comment pehle se hai (pichhla ledger "
                  f"push fail hua tha) — dobara nahi daala, sirf ledger update")
            continue
        try:
            post_comment(yt, r["video_id"], r.get("channel_id"), r["pinned_comment"])
            r["comment_posted"] = now
            done += 1
            print(f"[comments] posted on {r['video_id']} — pending se hata diya (Studio me pin karo)")
        except Exception as e:
            r["comment_error"] = str(e)[:200]
            r["comment_attempts"] = int(r.get("comment_attempts") or 0) + 1
            print(f"[comments] {r['video_id']} fail "
                  f"({r['comment_attempts']}/{COMMENT_MAX_ATTEMPTS}): {str(e)[:200]}")
            if "quotaExceeded" in str(e) or "dailyLimitExceeded" in str(e):
                # Quota khatam — baaki try karke agle upload ka quota mat khao
                print("[comments] quota khatam — baaki pending comments agle run me")
                break
    _save_ledger(rows)
    return done


def video_status(meta, privacy):
    """videos.insert ka status block.

    made_for_kids fallback C.MADE_FOR_KIDS (False): channel general audience
    ka hai (01-Oct-2026 faisla). Pehle default True tha — metadata me key na
    ho to video galti se "made for kids" ban jaata (comments band, RPM kam)."""
    return {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": bool(meta.get("made_for_kids", C.MADE_FOR_KIDS)),
    }


def _coverage_keys():
    """List-only YouTube read + ledger. Raises on API failure (fail closed)."""
    from googleapiclient.discovery import build
    from slot_planner import covered_from_ledger, covered_from_videos, fetch_videos
    yt = build("youtube", "v3", credentials=_creds(), cache_discovery=False)
    videos = fetch_videos(yt)
    return covered_from_videos(videos) | covered_from_ledger(_ledger())


def _refuse_duplicate(publish_at, target_slot, target_date, skip_coverage):
    """Exit 2 when this slot+date already has a public or scheduled video.

    Exit 1 when the check itself cannot run — uploading blind can duplicate
    a slot and burn the ~1600-unit insert.
    """
    if skip_coverage:
        return
    from slot_planner import nearest_slot, parse_time
    key = None
    if publish_at:
        key = nearest_slot(parse_time(publish_at))
    elif target_slot and target_date:
        key = (target_slot, target_date)
    if key is None:
        raise SystemExit(
            "[upload] public upload ke liye publishAt ya target slot+date chahiye "
            "— coverage check ke bina upload nahi karunga"
        )
    try:
        covered = _coverage_keys()
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(
            f"[upload] coverage check failed ({type(exc).__name__}: {exc}) "
            "— upload nahi kiya, duplicate se bachne ke liye"
        ) from None
    if key in covered:
        print(f"UPLOAD_SKIPPED=duplicate {key[0]} {key[1]}")
        raise SystemExit(2)


def upload(meta_path: Path, privacy="public", publish_at=None, target_slot=None,
           target_date=None, skip_coverage=False):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    video = Path(meta["video_file"])
    if not video.exists():
        video = meta_path.parent / video.name
    assert video.exists(), f"MP4 nahi mila: {video}"

    if privacy == "public":
        _refuse_duplicate(publish_at, target_slot, target_date, skip_coverage)

    status = video_status(meta, privacy)
    if publish_at:
        # YouTube: private + publishAt = exact time pe public
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at       # RFC3339, e.g. 2026-08-26T02:00:00Z
        print(f"[upload] privacy=private + publishAt={publish_at}")
    else:
        print(f"[upload] privacy={privacy} (no schedule — turant)")

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

    creds = _creds()
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    scopes = granted_scopes(creds)
    if scopes is not None:
        print(f"[upload] token scopes: {', '.join(sorted(x.rsplit('/', 1)[-1] for x in scopes))}")

    # Galat channel pe upload sabse mehnga error hai — pehle naam padh lo.
    channel_id = None
    try:
        ch = yt.channels().list(part="snippet", mine=True).execute()
        if ch.get("items"):
            channel_id = ch["items"][0]["id"]
            print(f"[upload] channel: {ch['items'][0]['snippet']['title']}")
    except Exception as e:
        print(f"[upload] channel naam nahi padh paaya (upload phir bhi try karenge): {e}")
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
    posted = None
    attempts = 0
    mfk = bool(meta.get("made_for_kids", C.MADE_FOR_KIDS))
    if pinned and not mfk:
        if scopes is not None and FORCE_SSL not in scopes:
            print("[upload] comment skip: token me youtube.force-ssl scope nahi hai. "
                  "`python src/upload.py --auth --set-github-secret` se naya token banao "
                  "(README: 'Pinned comment ke liye token'). Comment ledger me pending rahega.")
        else:
            try:
                post_comment(yt, vid, channel_id, pinned)
                posted = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                print("[upload] comment posted (pin manually — API pin nahi karta)")
            except Exception as e:
                # Scheduled/private video par comment reject ho sakta hai —
                # agla run public hone ke baad post_pending_comments() se daalega.
                attempts = 1
                print(f"[upload] comment abhi nahi gaya (baad me retry): {str(e)[:300]}")

    rows = _ledger()
    rows.append({
        "video_id": vid, "slot": meta.get("slot"), "date": meta.get("date"),
        "uploaded_ist": datetime.now(timezone.utc).astimezone(IST).strftime("%Y-%m-%d %H:%M"),
        "publish_at": publish_at, "privacy": privacy, "title": meta.get("title"),
        "subject": (meta.get("subjects") or [None])[0],
        "question_ids": meta.get("question_ids"), "hook_line": meta.get("hook_line"),
        "duration_sec": meta.get("duration_sec"), "channel_id": channel_id,
        "made_for_kids": mfk,
        "pinned_comment": pinned if not mfk else None,
        "comment_posted": posted,
        "comment_attempts": attempts,
    })
    _save_ledger(rows)

    meta["youtube_id"] = vid
    meta["youtube_url"] = f"https://youtube.com/shorts/{vid}"
    meta["scheduled_for"] = publish_at or f"immediate ({privacy})"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return vid


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--auth", action="store_true")
    ap.add_argument("--client-secret-file", default="client_secret.json")
    ap.add_argument("--set-github-secret", action="store_true",
                    help="--auth ke baad token seedha GitHub secret YOUTUBE_REFRESH_TOKEN me (gh CLI)")
    ap.add_argument("--post-pending-comments", action="store_true",
                    help="ledger ke jo comments reh gaye (video ab public), unhe post karo")
    ap.add_argument("--dir", type=Path)
    ap.add_argument("--privacy", default="public",
                    choices=["public", "private", "unlisted"])
    ap.add_argument("--publish-at", default=None,
                    help="RFC3339 UTC, e.g. 2026-08-28T15:00:00Z")
    ap.add_argument("--publish-slot", default=None,
                    help="slot ka naam — uske config.SLOTS wale IST time pe "
                         "YouTube khud public karega (GitHub cron late ho tab bhi)")
    ap.add_argument("--target-slot", default=None,
                    help="coverage key ka slot (immediate public upload)")
    ap.add_argument("--target-date", default=None,
                    help="coverage key ki IST date YYYY-MM-DD")
    ap.add_argument("--skip-coverage-check", action="store_true",
                    help="unlisted/private test upload — scheduled public slot skip")
    a = ap.parse_args()
    if a.auth:
        do_auth(a.client_secret_file, a.set_github_secret)
    elif a.post_pending_comments:
        try:
            post_pending_comments()
        except SystemExit as e:
            print(e)
        except Exception as e:
            print(f"[comments] skip: {type(e).__name__}: {str(e)[:200]}")
    elif a.dir:
        pub_at = a.publish_at
        # publishAt sirf tab jab video public hone wali ho. unlisted/private
        # test uploads pe scheduling ka koi matlab nahi.
        if not pub_at and a.publish_slot and a.privacy == "public":
            pub_at = resolve_publish_at(a.publish_slot)
        try:
            upload(a.dir / "metadata.json", a.privacy, pub_at,
                   target_slot=a.target_slot or a.publish_slot,
                   target_date=a.target_date,
                   skip_coverage=a.skip_coverage_check)
        except Exception as e:
            # Poora error stdout pe — CI logs blob storage pe hote hain, isliye
            # error ko file me bhi likhte hain jise workflow repo me commit karta hai.
            import traceback
            detail = traceback.format_exc()
            print(detail)
            body = getattr(getattr(e, "resp", None), "status", None)
            print(f"[upload] FAILED (http={body}): {e}")
            try:
                (a.dir / "upload_error.txt").write_text(detail, encoding="utf-8")
            except Exception:
                pass
            sys.exit(1)
    else:
        ap.error("--auth ya --dir me se ek do")
