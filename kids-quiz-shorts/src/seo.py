"""YouTube metadata. Sab template-based hai — koi API call nahi, isliye
deterministic aur free. Har slot (subah/shaam) ka alag hook taki duplicate
title na bane.

SEO logic:
- Title me search-intent keyword pehle 40 char me: "GK Question", "Class 1 to 5",
  "बच्चों के लिए". Shorts feed me title truncate hota hai, isliye hook aage.
- Description ke pehle 2 line hi search me count hoti hain — wahan keyword.
- Tags: broad -> specific. 15 tags, ~450 char, YouTube limit 500 hai.
- Hashtag: max 3 (3 se zyada daalo to YouTube sabko ignore kar deta hai).
"""
import random
from datetime import datetime

import config as C

HOOKS_MORNING = [
    "सुबह का GK सवाल",
    "आज का पहला सवाल",
    "स्कूल जाने से पहले ये बताओ",
    "क्या तुम्हें पता है?",
]
HOOKS_EVENING = [
    "शाम का GK चैलेंज",
    "होमवर्क के बाद ये सवाल",
    "आज का दूसरा सवाल",
    "90% बच्चे गलत करते हैं",
]

BASE_TAGS = [
    "gk questions in hindi", "gk for kids", "gk quiz hindi",
    "बच्चों के लिए जीके", "class 1 gk", "class 2 gk", "class 3 gk",
    "class 4 gk", "class 5 gk", "kids quiz hindi", "general knowledge for kids",
    "hindi quiz for children", "gk shorts", "बाल जीके", "primary school gk",
]

SUB_TAGS = {
    "GK":      ["gk questions hindi", "india gk for kids", "samanya gyan bachche"],
    "Science": ["science gk for kids", "vigyan quiz hindi", "science questions hindi"],
    "Maths":   ["maths quiz for kids", "ganit quiz hindi", "maths questions hindi"],
    "English": ["english for kids hindi", "english grammar quiz kids",
                "english word meaning hindi"],
}
SUB_HI = {"GK": "जीके", "Science": "विज्ञान", "Maths": "गणित", "English": "इंग्लिश"}


def build(questions, slot="morning", date=None):
    date = date or datetime.now()
    rng = random.Random(f"{date:%Y%m%d}{slot}")
    hooks = HOOKS_MORNING if slot == "morning" else HOOKS_EVENING
    hook = rng.choice(hooks)
    q1 = questions[0]["q"].rstrip("?")

    sub_hi = " + ".join(dict.fromkeys(SUB_HI.get(q.get("sub", "GK"), "जीके")
                                      for q in questions))
    title = f"{hook} 🤔 {q1}? | {sub_hi} Quiz Class 1-5 #shorts"
    if len(title) > 98:
        title = f"{hook} 🤔 {q1[:40]}…? | {sub_hi} Quiz #shorts"

    labels = ["A", "B", "C", "D"]
    q_block = "\n\n".join(
        f"सवाल {i+1} ({SUB_HI.get(q.get('sub','GK'),'जीके')}): {q['q']}\n"
        + "\n".join(f"{labels[j]}) {o}" for j, o in enumerate(q["opts"]))
        + f"\n✅ सही जवाब: {labels[q['ans']]}) {q['opts'][q['ans']]}"
        + (f"\n💡 क्यों: {q['why']}" if q.get("why") else "")
        for i, q in enumerate(questions)
    )

    engage = ("बच्चों, कितने सही हुए? घर में सबसे ये सवाल पूछो 🎯"
              if C.MADE_FOR_KIDS else "बच्चों, कितने सही हुए? कमेंट में लिखो 👇")

    description = f"""{hook} — कक्षा 1 से 5 तक के बच्चों के लिए आसान GK सवाल हिंदी में। हर सवाल पर 8 सेकंड का टाइमर, फिर सही जवाब।

रोज़ सुबह और शाम नए GK सवाल — चैनल सब्सक्राइब करो!

{q_block}

{engage}

इस चैनल पर मिलेगा:
• Class 1-5 के बच्चों के लिए GK, विज्ञान, गणित और इंग्लिश के सवाल
• हर जवाब के साथ एक लाइन में "क्यों" — सिर्फ़ रटना नहीं, समझना
• रोज़ 2 नए शॉर्ट्स — सुबह और शाम

#QuizPathshala #KidsQuiz #shorts"""

    subs = [q.get("sub", "GK") for q in questions]
    tags = list(BASE_TAGS)
    for c in dict.fromkeys(subs):
        tags += SUB_TAGS.get(c, [])
    seen, out_tags, total = set(), [], 0
    for t in tags:
        if t in seen:
            continue
        if total + len(t) + 1 > 460:
            break
        seen.add(t)
        out_tags.append(t)
        total += len(t) + 1

    # MFK videos pe comments band hote hain -> pinned comment ka koi matlab nahi
    pinned = None if C.MADE_FOR_KIDS else (
        f"बच्चों, दोनों सवाल सही हुए? 🎯\n"
        f"जवाब: 1) {labels[questions[0]['ans']]}  "
        f"2) {labels[questions[1]['ans']]}\n"
        f"रोज़ सुबह {C.SLOTS['morning']} और शाम {C.SLOTS['evening']} पर नया सवाल — "
        f"सब्सक्राइब करके बेल दबा दो 🔔"
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


if __name__ == "__main__":
    import json
    from pick import pick
    qs = pick(2, dry_run=True, slot='morning')
    print(json.dumps(build(qs, "morning"), ensure_ascii=False, indent=2))
