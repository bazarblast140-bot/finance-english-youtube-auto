"""QUIZ PATHSHALA — channel profile settings (About description, keywords,
default language, country, channel-level audience). NOTHING ELSE.

    python src/channel_settings.py                      # dry-run (default): sirf padho + diff dikhao
    python src/channel_settings.py --mode apply         # channels.update likho

!! Ye script KABHI video upload / edit nahi karti. Sirf ye API calls hoti hain:
!!   channels.list (1 unit), channels.update part=brandingSettings (50 units),
!!   channels.update part=status (50 units, sirf apply me, reject ho sakta hai)
!!   aur oauth2 tokeninfo (granted scopes dekhne ke liye, quota-free).
!! videos.insert / videos.update / channelBanners / thumbnails — kuch nahi.

Config: channel/channel_profile.json (audience = GENERAL, made-for-kids = false).

Auth: wahi YOUTUBE_* secrets jo kids-gk-shorts.yml upload ke liye use karta
hai (env YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN). Token value
kabhi print nahi hoti.
"""
import argparse
import difflib
import json
import os
import sys
from pathlib import Path

TOKEN_URI = "https://oauth2.googleapis.com/token"
TOKENINFO_URI = "https://oauth2.googleapis.com/tokeninfo"
# channels.update in me se KOI EK scope maangta hai (docs, 2026-09):
# https://developers.google.com/youtube/v3/docs/channels/update
WRITE_SCOPES = {
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtubepartner",
}
REAUTH_MSG = "needs re-auth with youtube.force-ssl"
REAUTH_STEPS = """\
Re-auth steps (QUIZ PATHSHALA wale Google account se, ek baar):
  1. Wahi OAuth client chahiye jo secrets YOUTUBE_CLIENT_ID/SECRET me hai (type: Desktop app).
     Google Cloud Console > APIs & Services > Credentials se uska client_secret.json
     download karke kids-quiz-shorts/ me rakho (commit mat karna).
  2. cd kids-quiz-shorts && python src/upload.py --auth
     PR #1 (fix/quiz-growth) wala upload.py use karo: scopes youtube.upload, youtube.readonly,
     youtube, youtube.force-ssl, aur token .yt_refresh_token file me likhta hai (print nahi).
     (main wala version force-ssl nahi maangta aur token terminal pe print karta hai.)
     Browser localhost ke random port pe redirect hota hai.
  3. Consent screen par SAARE checkbox tick karo, channel QUIZ PATHSHALA chuno, prompt par 'y'.
  4. Naya refresh token secret me daalo (value screen pe mat chhapo):
       gh secret set YOUTUBE_REFRESH_TOKEN -R bazarblast140-bot/finance-english-youtube-auto < .yt_refresh_token
     phir .yt_refresh_token delete karo. CLIENT_ID/SECRET same client ho to badalne ki zaroorat nahi.
     (PR #1 ka '--set-github-secret' abhi 'gh secret set ... --body -' chalata hai — gh '--body -' ko
      literal '-' maanta hai, secret kharab ho jaayega. Fix hone tak use mat karo.)
  5. Ye workflow phir se dry-run me chalao — 'granted scopes' me youtube / force-ssl dikhna chahiye."""

DESC_MAX = 1000
KEYWORDS_MAX = 500
# Ye fields hum config se likhte hain. Baaki (title, unsubscribedTrailer,
# trackingAnalyticsAccountId, ...) current value se waise ke waise jaate hain.
MANAGED_FIELDS = ("description", "keywords", "defaultLanguage", "country")
# brandingSettings.channel me sirf yahi settable hain (docs). title ko hum
# current value par hi rakhte hain (badla to channelTitleUpdateForbidden).
SETTABLE_CHANNEL_FIELDS = (
    "title", "description", "keywords", "trackingAnalyticsAccountId",
    "unsubscribedTrailer", "defaultLanguage", "country",
)


# ---------------------------------------------------------------- pure logic
def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    for k in ("channel_id", "expected_title", "brandingSettings"):
        if k not in cfg:
            raise ValueError(f"config me '{k}' nahi hai")
    return cfg


def proposed_channel(cfg):
    return dict(cfg["brandingSettings"].get("channel") or {})


def validate(channel_block):
    """Write se PEHLE fail karo. Errors ki list lautata hai (khaali = theek)."""
    errs = []
    d = channel_block.get("description")
    if d is not None:
        if len(d) > DESC_MAX:
            errs.append(f"description {len(d)} chars > {DESC_MAX}")
        if "<" in d or ">" in d:
            errs.append("description me '<' ya '>' hai (YouTube reject karta hai)")
    kw = channel_block.get("keywords")
    if kw is not None:
        if len(kw) > KEYWORDS_MAX:
            errs.append(f"keywords {len(kw)} chars > {KEYWORDS_MAX}")
        if kw.count('"') % 2:
            errs.append("keywords me unbalanced quote (\") hai — multi-word keyword truncate ho jaayega")
    return errs


def merge_channel(current, proposed):
    """channels.update poora part REPLACE karta hai — jo field nahi bheja wo
    delete ho jaata hai. Isliye current settable fields carry-over karo aur
    upar se sirf managed fields overlay karo. Title kabhi nahi badalte."""
    current = current or {}
    merged = {k: current[k] for k in SETTABLE_CHANNEL_FIELDS if current.get(k) not in (None, "")}
    for k in MANAGED_FIELDS:
        if k in proposed and proposed[k] is not None:
            merged[k] = proposed[k]
    if "title" in current:
        merged["title"] = current["title"]
    else:
        merged.pop("title", None)
    return merged


def field_diffs(before, after):
    """{field: unified-diff-text} sirf badle hue fields ke liye."""
    out = {}
    keys = list(MANAGED_FIELDS) + ["selfDeclaredMadeForKids"]
    for k in keys:
        if k not in after:
            continue
        a = "" if before.get(k) is None else str(before.get(k))
        b = "" if after.get(k) is None else str(after.get(k))
        if a == b:
            continue
        diff = difflib.unified_diff(
            a.splitlines() or [""], b.splitlines() or [""],
            fromfile=f"before/{k}", tofile=f"proposed/{k}", lineterm="")
        out[k] = "\n".join(diff)
    return out


def has_write_scope(scopes):
    """scopes: set ya None (tokeninfo fail). None -> pata nahi."""
    if scopes is None:
        return None
    return bool(WRITE_SCOPES & set(scopes))


def is_scope_error(status, text):
    t = (text or "").lower()
    return status == 403 and ("insufficientpermissions" in t
                              or "insufficient authentication scopes" in t
                              or "insufficient permission" in t)


# ---------------------------------------------------------------- API side
def get_creds():
    """upload.py ke _creds() jaisa: refresh token se, scopes param NAHI bhejte
    (Google jo granted hai wahi deta hai). Farq: yahan turant refresh karte
    hain taaki tokeninfo se granted scopes padh sakein aur dead token ka
    saaf message de sakein."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google.auth.exceptions import RefreshError
    missing = [k for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN") if not os.environ.get(k)]
    if missing:
        sys.exit(f"[channel] env missing: {', '.join(missing)} (GitHub secrets YOUTUBE_* set hain?)")
    creds = Credentials(
        None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri=TOKEN_URI,
    )
    try:
        creds.refresh(Request())
    except RefreshError as e:
        if "invalid_grant" in str(e):
            print("[channel] token expired/revoked — re-auth needed")
            print(REAUTH_STEPS)
            sys.exit(1)
        if "invalid_client" in str(e) or "unauthorized_client" in str(e):
            sys.exit("[channel] OAuth client galat hai (YOUTUBE_CLIENT_ID/SECRET) — refresh token isi client se bana hona chahiye")
        raise
    return creds


def granted_scopes(creds):
    try:
        import requests
        r = requests.get(TOKENINFO_URI, params={"access_token": creds.token}, timeout=15)
        if r.ok:
            return set(r.json().get("scope", "").split())
        print(f"[channel] tokeninfo http {r.status_code} — scopes pata nahi chale")
    except Exception as e:  # network etc.
        print(f"[channel] tokeninfo fail: {type(e).__name__}")
    return None


def _http_reason(e):
    status = getattr(getattr(e, "resp", None), "status", None)
    try:
        body = e.content.decode("utf-8", "ignore") if isinstance(e.content, bytes) else str(e.content)
    except Exception:
        body = str(e)
    reason = ""
    try:
        reason = json.loads(body)["error"]["errors"][0].get("reason", "")
    except Exception:
        pass
    return status, reason, body


def show(label, value):
    if isinstance(value, str) and "\n" in value:
        print(f"  {label}:")
        for line in value.splitlines():
            print(f"      | {line}")
    else:
        print(f"  {label}: {value if value not in (None, '') else '(empty)'}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    ap.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "channel" / "channel_profile.json"))
    a = ap.parse_args(argv)

    cfg = load_config(a.config)
    proposed = proposed_channel(cfg)
    want_mfk = (cfg.get("status") or {}).get("selfDeclaredMadeForKids")
    print(f"[channel] mode={a.mode}  config={a.config}")
    print("[channel] quota: channels.list = 1 unit, har channels.update = 50 units. Koi upload nahi.")

    errs = validate(proposed)
    if errs:
        print("[channel] CONFIG INVALID — kuch nahi likha:")
        for e in errs:
            print("   -", e)
        return 1

    creds = get_creds()
    scopes = granted_scopes(creds)
    if scopes is not None:
        print("[channel] granted scopes:", " ".join(sorted(scopes)) or "(none)")
    can_write = has_write_scope(scopes)
    if can_write is False:
        print(f"[channel] WARNING: {REAUTH_MSG} — token me youtube / youtube.force-ssl nahi hai, apply 403 dega.")

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    resp = yt.channels().list(part="snippet,brandingSettings,status", mine=True).execute()
    items = resp.get("items") or []
    if not items:
        print("[channel] is token ka koi channel nahi mila")
        return 1
    ch = items[0]
    title = (ch.get("snippet") or {}).get("title")
    if ch.get("id") != cfg["channel_id"] or title != cfg["expected_title"]:
        print(f"[channel] WRONG CHANNEL: token -> {title!r} ({ch.get('id')}), "
              f"config -> {cfg['expected_title']!r} ({cfg['channel_id']}). Abort, kuch nahi likha.")
        return 1

    current = (ch.get("brandingSettings") or {}).get("channel") or {}
    status = ch.get("status") or {}
    snippet = ch.get("snippet") or {}
    print(f"\n=== BEFORE  ({title}, {ch['id']}, {snippet.get('customUrl', '')}) ===")
    print("  brandingSettings.channel (full):")
    print(json.dumps(current, ensure_ascii=False, indent=2))
    show("snippet.defaultLanguage", snippet.get("defaultLanguage"))
    show("snippet.country", snippet.get("country"))
    show("status.madeForKids", status.get("madeForKids", "(not returned)"))
    show("status.selfDeclaredMadeForKids", status.get("selfDeclaredMadeForKids", "(not returned)"))

    merged = merge_channel(current, proposed)
    print("\n=== PROPOSED ===")
    for k in MANAGED_FIELDS:
        show(k, merged.get(k))
    show("status.selfDeclaredMadeForKids", want_mfk)

    before_flat = dict(current)
    before_flat["selfDeclaredMadeForKids"] = status.get("selfDeclaredMadeForKids")
    after_flat = dict(merged)
    if want_mfk is not None:
        after_flat["selfDeclaredMadeForKids"] = want_mfk
    diffs = field_diffs(before_flat, after_flat)
    print("\n=== DIFF ===")
    if not diffs:
        print("  (koi farq nahi)")
    for k, d in diffs.items():
        print(f"--- {k}")
        print(d)

    if a.mode != "apply":
        print("\n[channel] DRY-RUN — kuch nahi likha.")
        if can_write is False:
            print(f"[channel] {REAUTH_MSG}")
            print(REAUTH_STEPS)
        return 0

    # ------------------------------------------------------------ APPLY
    if can_write is False:
        # tokeninfo ne saaf bataya ki write scope nahi hai — 403 pe quota
        # kharch karne ka koi matlab nahi.
        print(f"\n[channel] APPLY rok diya: {REAUTH_MSG}")
        print(REAUTH_STEPS)
        return 1
    print("\n[channel] APPLY: channels.update part=brandingSettings ...")
    body = {"id": ch["id"], "brandingSettings": {"channel": merged}}
    try:
        yt.channels().update(part="brandingSettings", body=body).execute()
        print("[channel] brandingSettings updated")
    except HttpError as e:
        st, reason, text = _http_reason(e)
        if is_scope_error(st, text):
            print(f"[channel] 403 insufficientPermissions — {REAUTH_MSG}")
            print(REAUTH_STEPS)
            return 1
        print(f"[channel] channels.update FAILED http={st} reason={reason or '?'}")
        print(text[:1500])
        return 1

    mfk_ok = True
    if want_mfk is not None:
        print(f"[channel] channels.update part=status selfDeclaredMadeForKids={want_mfk} ...")
        try:
            yt.channels().update(part="status", body={
                "id": ch["id"], "status": {"selfDeclaredMadeForKids": bool(want_mfk)}}).execute()
            print("[channel] status.selfDeclaredMadeForKids updated")
        except HttpError as e:
            st, reason, text = _http_reason(e)
            mfk_ok = False
            if is_scope_error(st, text):
                print(f"[channel] status update 403 — {REAUTH_MSG}")
            else:
                print(f"[channel] status update http={st} reason={reason or '?'}")
            print("[channel] API ne channel-level audience update reject kiya — YouTube Studio > "
                  "Settings > Channel > Advanced settings > 'No, set this channel as not made for kids' "
                  "manually karo. (brandingSettings update phir bhi ho chuka hai.)")

    after = yt.channels().list(part="snippet,brandingSettings,status", mine=True).execute()["items"][0]
    ac = (after.get("brandingSettings") or {}).get("channel") or {}
    print("\n=== AFTER ===")
    for k in MANAGED_FIELDS:
        show(k, ac.get(k))
    show("status.madeForKids", (after.get("status") or {}).get("madeForKids", "(not returned)"))
    show("status.selfDeclaredMadeForKids", (after.get("status") or {}).get("selfDeclaredMadeForKids", "(not returned)"))
    if not mfk_ok:
        print("[channel] NOTE: made-for-kids Studio me manually set karna baaki hai.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
