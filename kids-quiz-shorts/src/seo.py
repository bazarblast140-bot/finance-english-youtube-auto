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

HOOKS = {
    "morning": ["सुबह का GK सवाल", "स्कूल जाने से पहले ये बताओ",
                "आज का पहला सवाल", "क्या तुम्हें पता है?"],
    "noon":    ["दोपहर का क्विज़ ब्रेक", "लंच टाइम चैलेंज",
                "ये आसान सा सवाल", "80% बच्चे यहाँ अटक जाते हैं"],
    "evening": ["स्कूल के बाद ये सवाल", "होमवर्क से पहले एक सवाल",
                "शाम का GK चैलेंज", "90% बच्चे गलत करते हैं"],
    "night":   ["सोने से पहले एक सवाल", "आज का आखिरी सवाल",
                "रात का क्विज़ चैलेंज", "ये आता है तुम्हें?"],
}

# Specific -> broad. 8 tags kaafi hain; "class 1 gk ... class 5 gk" jaise
# paanch alag tags sirf budget khaate the, koi naya audience nahi laate.
BASE_TAGS = [
    "gk quiz for kids in hindi",
    "बच्चों के लिए जीके सवाल",
    "class 1 to 5 gk questions",
    "hindi gk quiz with answers",
    "kids general knowledge hindi",
]

SUB_TAGS = {
    "GK":      ["samanya gyan quiz hindi", "india gk for kids"],
    "Science": ["vigyan quiz hindi bachche", "science gk for kids hindi"],
    "Maths":   ["ganit quiz for kids hindi", "maths questions for class 1 to 5"],
    "English": ["english word meaning in hindi", "english grammar for kids hindi"],
}

# 4 hashtag: broad -> niche -> subject -> brand. #shorts jaan-boojh ke nahi.
SUB_HASH = {"GK": "#GeneralKnowledge", "Science": "#ScienceForKids",
            "Maths": "#MathsQuiz", "English": "#EnglishForKids"}
SUB_HI = {"GK": "जीके", "Science": "विज्ञान", "Maths": "गणित", "English": "इंग्लिश"}


def build(questions, slot="morning", date=None):
    date = date or datetime.now()
    rng = random.Random(f"{date:%Y%m%d}{slot}")
    hook = rng.choice(HOOKS.get(slot, HOOKS["morning"]))
    labels = ["A", "B", "C", "D"]

    q1 = questions[0]
    qtext = q1["q"].strip()
    subs = list(dict.fromkeys(q.get("sub", "GK") for q in questions))
    sub_hi = " + ".join(SUB_HI.get(x, "जीके") for x in subs)

    # --- TITLE: sawaal pehle -------------------------------------------------
    # Mobile Shorts feed me title ki ek line dikhti hai. Isliye sawaal poora
    # aage, aur context (subject/class) baad me — truncate ho bhi jaaye to
    # viewer ne asli hook padh liya hota hai.
    tail = f" | {sub_hi} क्विज़ Class 1-5"
    if len(qtext) + len(tail) > 96:
        tail = f" | {sub_hi} क्विज़"
    title = f"{qtext} 🤔{tail}"
    if len(title) > 100:
        title = f"{qtext[:100 - len(tail) - 4]}…{tail}"

    # --- DESCRIPTION ---------------------------------------------------------
    q_block = "\n\n".join(
        f"सवाल {i+1} ({SUB_HI.get(q.get('sub','GK'),'जीके')}): {q['q']}\n"
        + "\n".join(f"{labels[j]}) {o}" for j, o in enumerate(q["opts"]))
        + f"\n✅ सही जवाब: {labels[q['ans']]}) {q['opts'][q['ans']]}"
        + (f"\n💡 क्यों: {q['why']}" if q.get("why") else "")
        for i, q in enumerate(questions)
    )
    engage = ("बच्चों, कितने सही हुए? घर में सबसे ये सवाल पूछो 🎯"
              if C.MADE_FOR_KIDS else "कितने सही हुए? कमेंट में लिखो 👇")

    # Pehli line me hi keyword + sawaal — ye ~100 char sabse zyada weight
    # rakhte hain, isliye yahan "hook" nahi, saaf topic likhte hain.
    slot_times = ", ".join(C.SLOTS[k] for k in C.SLOT_ORDER)
    first = (f"कक्षा 1 से 5 के बच्चों के लिए {sub_hi} क्विज़ हिंदी में — {qtext} "
             f"हर सवाल पर 8 सेकंड का टाइमर, फिर सही जवाब और वजह।")

    description = f"""{first}

{hook} रोज़ {C.VIDEOS_PER_DAY} नए सवाल — {C.BRAND} को सब्सक्राइब करो! 🔔

{q_block}

{engage}

इस चैनल पर मिलेगा:
• GK, विज्ञान, गणित और इंग्लिश — चारों के सवाल, कक्षा 1 से 5 तक
• हर जवाब के साथ एक लाइन में "क्यों" — सिर्फ़ रटना नहीं, समझना
• रोज़ {C.VIDEOS_PER_DAY} नए शॉर्ट्स — {slot_times}

{hashtags(subs)}"""

    # --- TAGS ----------------------------------------------------------------
    tags = list(BASE_TAGS)
    if any(q.get("topic") == "सबसे" for q in questions):
        tags = ["duniya me sabse bada kaun sa hai", "sabse uncha lamba gehra"] + tags
    for c in subs:
        tags += SUB_TAGS.get(c, [])
    seen, out_tags, total = set(), [], 0
    for t in tags:
        if t in seen or total + len(t) + 1 > 460:
            continue
        seen.add(t); out_tags.append(t); total += len(t) + 1
        if len(out_tags) == 8:        # volume nahi, relevance — 8 pe rok do
            break

    pinned = None if C.MADE_FOR_KIDS else (
        f"जवाब: 1) {labels[questions[0]['ans']]}  "
        f"2) {labels[questions[1]['ans']]}\n"
        f"दोनों सही? रोज़ {C.VIDEOS_PER_DAY} नए सवाल आते हैं 🔔\n"
        f"किस subject के सवाल और चाहिए — GK, विज्ञान, गणित या इंग्लिश?"
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


def hashtags(subs):
    """4 hashtag: broad -> niche -> subject -> brand.

    15 se upar gaye to YouTube saare ignore kar deta hai, isliye ginti kam
    rakhna hi surakshit hai. #shorts nahi lagate — YouTube ab ratio aur
    duration se Short pehchanta hai, aur wo tag har Short pe lag sakta hai
    isliye categorisation me kuch batata nahi.
    """
    tags = ["#GKInHindi", "#KidsQuiz"]
    tags.append(SUB_HASH.get(subs[0], "#GeneralKnowledge"))
    tags.append("#QuizPathshala")
    return " ".join(dict.fromkeys(tags))


if __name__ == "__main__":
    import json
    from pick import pick
    qs = pick(2, dry_run=True, slot='noon')
    print(json.dumps(build(qs, "morning"), ensure_ascii=False, indent=2))
