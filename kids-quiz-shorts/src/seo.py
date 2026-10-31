"""YouTube metadata. Sab template-based — koi API call nahi, deterministic aur free.

Ye rules 2026 ke Shorts behaviour pe based hain, purane long-form SEO pe nahi:

1. HASHTAG: 3-5 se zyada ka koi fayda nahi. 15 se upar gaye to YouTube
   video ke SAARE hashtag ignore kar deta hai — pehle teen bhi. Hum 4 use
   karte hain: broad -> niche -> subject -> brand.
2. #shorts NAHI lagate. YouTube ab aspect ratio (9:16) aur duration se
   Short pehchanta hai; #shorts sirf title/hashtag budget khaata hai aur
   categorisation me zero madad karta hai (har Short use kar sakta hai).
3. TAGS (hidden metadata): 21 generic tags se 8 specific tags behtar hain.
   Tag volume nahi, relevance count hoti hai. Irrelevant tag ulta galat
   audience tak le jaata hai -> low retention -> algorithm neeche kar deta hai.
4. TITLE: sawaal SABSE PEHLE. Shorts feed me mobile pe title ki ek hi line
   dikhti hai (~45-55 char), isliye "क्या तुम्हें पता है?" jaisa hook aage
   rakha to asli sawaal truncate ho jaata hai. Sawaal khud hi hook hai.
5. DESCRIPTION: pehle ~100 character sabse zyada weight rakhte hain —
   wahan keyword + sawaal, na ki generic tagline.

Sabse zaroori baat: ye sab CHHOTA lever hai. Shorts me discovery mainly
retention aur swipe-away rate se chalti hai. SEO sirf ye tay karta hai ki
video KIS audience ko dikhe; wo audience rukegi ya nahi, wo video pe hai.
"""
import random
from datetime import datetime

import config as C

# 30-Sep-2026: "स्कूल जाने से पहले", "होमवर्क से पहले", "90% बच्चे गलत करते हैं"
# hata diye. (1) Channel 29-Aug ko general Hindi GK par pivot ho chuka hai aur
# MADE_FOR_KIDS=False hai — metadata me bacchon ko target karna usi label ke
# khilaaf gawahi hai (COPPA risk). (2) "90%" jaisi nakli statistic viewer ko
# ek baar hi bewakoof banati hai.
HOOKS = {
    "morning": ["सुबह का GK सवाल", "आज का पहला सवाल", "चाय के साथ एक सवाल"],
    "noon":    ["दोपहर का क्विज़ ब्रेक", "लंच ब्रेक चैलेंज", "दिमाग़ को 8 सेकंड दो"],
    "paheli":  ["आज की पहेली बूझिए", "दिमाग़ी पहेली — सोचिए तो सही",
                "ये पहेली दोस्तों से पूछिए"],
    "evening": ["शाम का GK चैलेंज", "ये सवाल दोस्तों से पूछिए"],
    "night":   ["सोने से पहले एक सवाल", "आज का आख़िरी सवाल", "ये आता है आपको?"],
}

# Title ki poonchh (tail) — Hinglish keyword jo log sach me search karte hain
# ("world gk quiz", "science gk"). Pehle "| दुनिया + सामान्य ज्ञान क्विज़" tha:
# lamba, do subject jode hue, aur search keyword (GK/quiz) Latin me tha hi nahi.
TITLE_TAIL = {
    "सामान्य ज्ञान": "GK Quiz Hindi",
    "विज्ञान":      "Science GK Quiz",
    "भारत":        "India GK Quiz",
    "दुनिया":       "World GK Quiz",
    "पहेली":        "Hindi Paheli",
}

# Specific -> broad. 8 tags kaafi hain; "class 1 gk ... class 5 gk" jaise
# paanch alag tags sirf budget khaate the, koi naya audience nahi laate.
BASE_TAGS = [
    "gk question in hindi",
    "सामान्य ज्ञान के सवाल",
    "gk quiz hindi with answer",
    "general knowledge hindi",
    "gk questions for competitive exams",
    "hindi quiz",
]

SUB_TAGS = {
    "सामान्य ज्ञान": ["samanya gyan quiz", "gk ke sawal hindi"],
    "विज्ञान":      ["science gk in hindi", "vigyan ke rochak tathya"],
    "भारत":        ["india gk in hindi", "bharat samanya gyan"],
    "दुनिया":       ["world gk in hindi", "duniya ke rochak tathya"],
    "पहेली":        ["paheli in hindi", "hindi riddles with answer"],
}

# 4 hashtag: broad -> niche -> subject -> brand. #shorts jaan-boojh ke nahi.
SUB_HASH = {"सामान्य ज्ञान": "#SamanyaGyan", "विज्ञान": "#ScienceGK",
            "भारत": "#IndiaGK", "दुनिया": "#WorldGK", "पहेली": "#Paheli"}
SUB_HI = {k: k for k in
          ["सामान्य ज्ञान", "विज्ञान", "भारत", "दुनिया", "पहेली"]}


def build(questions, slot="morning", date=None):
    date = date or datetime.now()
    rng = random.Random(f"{date:%Y%m%d}{slot}")
    # Hook pehle sirf slot se aata tha. Ab morning aur night me bhi paheli
    # jaati hai (config.PAHELI_SLOTS), aur riddle par "सुबह का GK सवाल" galat
    # hook hai — isliye content dekhkar chunte hain, slot ke naam se nahi.
    is_paheli = slot in getattr(C, "PAHELI_SLOTS", ["paheli"]) or any(
        q.get("sub") == C.PAHELI_SUB for q in questions)
    hook = rng.choice(HOOKS["paheli"] if is_paheli
                      else HOOKS.get(slot, HOOKS["morning"]))
    labels = ["A", "B", "C", "D"]

    q1 = questions[0]
    qtext = q1["q"].strip()
    subs = list(dict.fromkeys(q.get("sub", "GK") for q in questions))
    sub_hi = " + ".join(SUB_HI.get(x, "जीके") for x in subs)

    # --- TITLE: search keyword pehle (31-Oct-2026 growth) --------------------
    # "GK Quiz in Hindi | <sawaal> 🤔 | GK Question Answer" — log yahi
    # phrase search karte hain. Subject ke hisaab se variant; sawaal ko
    # chhota karte hain taaki poora title <=100 char rahe.
    head, tail = title_parts(q1.get("sub"), is_paheli)
    title = fit_title(head, qtext, tail)

    # --- DESCRIPTION ---------------------------------------------------------
    q_block = "\n\n".join(
        f"सवाल {i+1} ({SUB_HI.get(q.get('sub','GK'),'जीके')}): {q['q']}\n"
        + "\n".join(f"{labels[j]}) {o}" for j, o in enumerate(q["opts"]))
        + f"\n✅ सही जवाब: {labels[q['ans']]}) {q['opts'][q['ans']]}"
        + (f"\n💡 क्यों: {q['why']}" if q.get("why") else "")
        for i, q in enumerate(questions)
    )
    engage = "कितने सही हुए? कमेंट में लिखिए 👇"

    # Pehli line me hi keyword + sawaal — ye ~100 char sabse zyada weight
    # rakhte hain, isliye yahan "hook" nahi, saaf topic likhte hain.
    slot_times = ", ".join(C.SLOTS[k] for k in C.ACTIVE_SLOTS)
    # video me "इशारा" band ho (fauji CTA) to वजह sirf neeche description me hai
    tail = ("फिर सही जवाब और वजह।" if getattr(C, "HINT_BEFORE_ANSWER", True)
            else "फिर सही जवाब — वजह नीचे।")
    more = ""
    if len(questions) > 1:
        more = " बोनस: " + " • ".join(q["q"].strip() for q in questions[1:])
    if is_paheli:
        first = (f"दिमाग़ घुमाने वाली हिंदी पहेली — {qtext}{more} "
                 f"{C.TIMER_SECONDS} सेकंड का टाइमर, {tail}")
    else:
        first = (f"{sub_hi} क्विज़ हिंदी में (GK Quiz in Hindi) — {qtext}{more} "
                 f"हर सवाल पर {C.TIMER_SECONDS} सेकंड का टाइमर, {tail}")

    description = f"""{first}

{hook}! रोज़ नए सवालों के लिए {C.BRAND} को सब्सक्राइब कीजिए 🔔

{q_block}

{engage}

इस चैनल पर मिलेगा:
• सामान्य ज्ञान, विज्ञान, भारत, दुनिया और पहेलियाँ
• हर जवाब के साथ एक लाइन में "क्यों" — सिर्फ़ रटना नहीं, समझना
• रोज़ {C.VIDEOS_PER_DAY} नए शॉर्ट्स — {slot_times}

{hashtags(subs)}"""

    # --- TAGS ----------------------------------------------------------------
    tags = list(BASE_TAGS)
    if is_paheli:
        # "hindi riddles for class 1 to 5" hataya — MADE_FOR_KIDS=False ke
        # saath bacchon ki class wala tag ulta signal tha.
        tags = ["paheli in hindi with answer", "दिमागी पहेलियाँ हिंदी",
                "hindi riddles with answer"] + tags
    if any(q.get("topic") == "सबसे" for q in questions):
        tags = ["duniya me sabse bada kaun sa hai", "sabse uncha lamba gehra"] + tags
    for c in subs:
        tags += SUB_TAGS.get(c, [])
    # Optional: competitor research (data/competitor_insights.json) se 1-2
    # relevant tag. Sirf allowlist wale shabd (gk/quiz/paheli...) — kisi
    # doosre channel ka naam/brand kabhi nahi. File na ho to kuch nahi hota.
    try:
        from competitor_research import insight_tags
        tags += insight_tags(max_n=2)
    except Exception:
        pass
    seen, out_tags, total = set(), [], 0
    for t in tags:
        if t in seen or total + len(t) + 1 > 460:
            continue
        seen.add(t); out_tags.append(t); total += len(t) + 1
        if len(out_tags) == 10:       # volume nahi, relevance — 10 pe rok do
            break

    # NOTE: kisi bhi question count ke saath chalna chahiye. Pehle yahan
    # hardcoded questions[1] tha, jo QUESTIONS_PER_VIDEO=1 hote hi IndexError
    # de raha tha — video ban jaata tha par metadata.json likha hi nahi jaata.
    # Pehle pinned comment me seedha "जवाब: 1) C 2) A" tha — comments kholte hi
    # jawab mil jaata tha, to kisi ko apna jawab likhne ki wajah nahi bachti
    # thi. Ab sawaal poochte hain (comment = engagement signal), jawab video me.
    n_q = len(questions)
    ask = ("जवाब कमेंट करें 👇 A, B, C या D — आपका जवाब क्या है?" if n_q == 1 else
           f"जवाब कमेंट करें 👇 {n_q} में से कितने सही हुए? अपना स्कोर कमेंट कीजिए 👇")
    pinned = None if C.MADE_FOR_KIDS else (
        f"{ask}\n"
        f"रोज़ नए सवाल आते हैं — सब्सक्राइब करके रोज़ खेलिए 🔔\n"
        f"किस विषय के सवाल और चाहिए — भारत, विज्ञान, दुनिया या पहेली?"
    )

    return {
        "title": title[:100],
        "description": description[:4900],
        "tags": out_tags,
        "categoryId": "27",           # Education
        "pinned_comment": pinned,
        "made_for_kids": C.MADE_FOR_KIDS,
        "slot": slot,
        "date": f"{date:%Y-%m-%d}",
        "question_ids": [q["id"] for q in questions],
    }


# (head, tail) per subject. Paheli ke liye alag search phrase.
TITLE_VARIANTS = {
    "विज्ञान": ("Science GK Quiz in Hindi", "Science GK Question Answer"),
    "भारत":   ("India GK Quiz in Hindi", "India GK Question Answer"),
    "दुनिया":  ("World GK Quiz in Hindi", "World GK Question Answer"),
    "पहेली":   ("Hindi Paheli Quiz", "Paheli with Answer"),
}
DEFAULT_TITLE = ("GK Quiz in Hindi", "GK Question Answer")


def title_parts(sub, is_paheli=False):
    if is_paheli:
        return TITLE_VARIANTS["पहेली"]
    return TITLE_VARIANTS.get(sub, DEFAULT_TITLE)


def fit_title(head, qtext, tail, emoji="🤔", limit=100):
    """head | sawaal emoji | tail — sawaal truncate karke limit me fit."""
    qtext = " ".join(qtext.split())
    fixed = f"{head} |  {emoji} | {tail}"
    room = limit - len(fixed)
    if len(qtext) > room:
        qtext = qtext[:max(0, room - 1)].rstrip() + "…"
    t = f"{head} | {qtext} {emoji} | {tail}"
    if len(t) > limit:                 # bahut lamba sawaal: tail chhod do
        t = f"{head} | {qtext}"[:limit]
    return t


# 31-Oct-2026: fixed hashtag set (Rajesh). Sirf 6 — 15 ki limit se kaafi neeche.
FIXED_HASHTAGS = "#gkquiz #gkinhindi #gkquestion #quiz #paheli #shorts"
KEYWORD_LINE = ("GK Quiz in Hindi | GK Question Answer | Hindi Paheli | "
                "सामान्य ज्ञान प्रश्न उत्तर")


def hashtags(subs=None):
    """Fixed set + ek keyword line (subject-independent)."""
    return f"{KEYWORD_LINE}\n{FIXED_HASHTAGS}"


def _old_hashtags(subs):
    """4 hashtag: broad -> niche -> subject -> brand.

    15 se upar gaye to YouTube saare ignore kar deta hai, isliye ginti kam
    rakhna hi surakshit hai. #shorts nahi lagate — YouTube ab ratio aur
    duration se Short pehchanta hai, aur wo tag har Short pe lag sakta hai
    isliye categorisation me kuch batata nahi.
    """
    tags = ["#GKInHindi", "#GKQuestion"]
    if "पहेली" in subs:
        # #KidsQuiz hataya — pivot ke baad audience general hai, aur ye
        # hashtag YouTube ko galat audience ka signal deta tha.
        tags = ["#पहेली", "#दिमागीपहेली", "#HindiPaheli"]
    else:
        tags.append(SUB_HASH.get(subs[0], "#GeneralKnowledge"))
    tags.append("#QuizPathshala")
    return " ".join(dict.fromkeys(tags))


if __name__ == "__main__":
    import json
    from pick import pick
    qs = pick(2, dry_run=True, slot='noon')
    print(json.dumps(build(qs, "morning"), ensure_ascii=False, indent=2))
