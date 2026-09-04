"""Purane live videos ki description me se bachi hui purani framing hatata hai.

Kyun ye alag script hai: pivot (kids -> general GK) ke baad naye videos to
theek ban rahe hain, par jo pehle publish ho chuke hain unki description me
purana text hi pada hai. Wo YouTube ko channel ka topic galat batata hai.

Chalane ka tareeka (Actions -> Fix Old Descriptions):
    python src/fix_descriptions.py            # dry run — sirf dikhata hai
    python src/fix_descriptions.py --apply    # sach me badalta hai

Quota: videos.list 1 unit, videos.update 50 units per video. 20 video = ~1020
units. Daily limit 10,000 hai aur roz ke 5 upload 8,000 lete hain — isliye
ise upload slots se alag time par chalana behtar hai.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from upload import _creds  # wahi OAuth jo upload.py use karta hai

# (purana text, naya text). Sirf poori line replace hoti hai, taaki har video
# ka apna sawaal-jawab wala hissa bilkul na chhide.
REPLACEMENTS = [
    ("• GK, विज्ञान, गणित, इंग्लिश और पहेलियाँ — कक्षा 1 से 5 तक",
     "• सामान्य ज्ञान, विज्ञान, भारत, दुनिया और पहेलियाँ"),
    ("• GK, विज्ञान, गणित और इंग्लिश — चारों के सवाल, कक्षा 1 से 5 तक",
     "• सामान्य ज्ञान, विज्ञान, भारत, दुनिया और पहेलियाँ"),
    ("• Class 1-5 के बच्चों के लिए GK questions in Hindi",
     "• सामान्य ज्ञान, विज्ञान, भारत और दुनिया के रोचक सवाल"),
    ("बच्चों की दिमागी पहेली हिंदी में", "दिमाग़ घुमाने वाली हिंदी पहेली"),
    ("कक्षा 1 से 5 के बच्चों के लिए ", ""),
]
TITLE_REPLACEMENTS = [
    (" | बच्चों की पहेली Class 1-5", " | हिंदी पहेली"),
    (" | GK Quiz Class 1-5", " | GK क्विज़"),
    (" Class 1-5", ""),
]


def fix(text, rules):
    out = text
    for old, new in rules:
        out = out.replace(old, new)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="bina iske sirf dry run hota hai")
    ap.add_argument("--limit", type=int, default=100,
                    help="kitne video SCAN karne hain")
    ap.add_argument("--max", type=int, default=35,
                    help="ek run me kitne UPDATE karne hain. Har update 50 "
                         "quota units leta hai aur roz ke 5 upload pehle hi "
                         "8,000 units le jaate hain (limit 10,000) — isliye "
                         "ek hi run me sab karna quota tod deta hai.")
    a = ap.parse_args()

    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=_creds(), cache_discovery=False)

    ch = yt.channels().list(part="contentDetails,snippet", mine=True).execute()
    uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    print(f"channel: {ch['items'][0]['snippet']['title']}")

    ids, token = [], None
    while len(ids) < a.limit:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                    maxResults=50, pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        token = r.get("nextPageToken")
        if not token:
            break

    print(f"{len(ids)} video mile\n")
    changed = skipped = failed = 0
    for i in range(0, len(ids), 50):
        batch = yt.videos().list(part="snippet,status",
                                 id=",".join(ids[i:i + 50])).execute()
        for v in batch["items"]:
            sn = v["snippet"]
            new_desc = fix(sn.get("description", ""), REPLACEMENTS)
            new_title = fix(sn.get("title", ""), TITLE_REPLACEMENTS)[:100]
            if new_desc == sn.get("description", "") and new_title == sn["title"]:
                skipped += 1
                continue
            print(f"  {v['id']}  {sn['title'][:52]}")
            if new_title != sn["title"]:
                print(f"      title -> {new_title[:60]}")
            if not a.apply:
                changed += 1
                continue
            if changed >= a.max:
                print(f"      (--max {a.max} pahunch gaya, baaki agle run me)")
                skipped += 1
                continue
            try:
                # videos.update poora snippet maangta hai — jo field na bhejo
                # wo CLEAR ho jaata hai, isliye sab wapas bhej rahe hain.
                body = {"id": v["id"], "snippet": {
                    "title": new_title,
                    "description": new_desc,
                    "categoryId": sn.get("categoryId", "27"),
                    "tags": sn.get("tags", []),
                    "defaultLanguage": sn.get("defaultLanguage", "hi"),
                    "defaultAudioLanguage": sn.get("defaultAudioLanguage", "hi"),
                }}
                yt.videos().update(part="snippet", body=body).execute()
                changed += 1
            except Exception as e:
                failed += 1
                print(f"      FAIL: {e}")
                if "insufficientPermissions" in str(e) or "insufficient" in str(e):
                    # Ye har video par same fail hoga — 65 identical error
                    # chhapne ka koi matlab nahi.
                    print("\n  RUK GAYE: refresh token me WRITE scope nahi hai.\n"
                          "  videos.update ke liye 'youtube' scope chahiye; abhi\n"
                          "  sirf upload + readonly granted hai. Isi wajah se\n"
                          "  pinned comment bhi 403 deta hai.\n\n"
                          "  Theek karne ke liye laptop par:\n"
                          "    python src/upload.py --auth\n"
                          "  phir naye YOUTUBE_CLIENT_ID / SECRET / REFRESH_TOKEN\n"
                          "  repo Secrets me update karo, aur ye workflow dobara chalao.")
                    return 1

    mode = "badle" if a.apply else "badle JAATE (dry run)"
    print(f"\n{changed} {mode} | {skipped} chhode/pehle se theek | {failed} fail")
    if a.apply:
        print(f"quota kharch: lagbhag {changed * 50 + len(ids)//50 + 1} units")
    if not a.apply:
        print("Sach me badalne ke liye --apply lagao.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
