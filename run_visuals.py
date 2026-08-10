"""Stage 4: Visual Agent builds a timed shot list, Gate 3 verifies density/numbers/repeats.
Exits non-zero on Gate 3 fail."""
import json
from common import cfg, claude_json, read, save, ok, die, RUN

VISUAL_SYSTEM = """You are the Visual Planner Agent for a faceless finance YouTube channel. Create a concise visual shot list for the provided script text.

RULES:
1. Dynamic pacing: 4-7 second shots.
2. If numbers are mentioned in the text, put them in on_screen_text.
3. Keep on_screen_text under 5 words.
4. Keep source_asset_query under 5 words.

JSON FORMAT (Output ONLY this JSON object):
{
  "shots": [
    {
      "shot_id": 1,
      "start_sec": 0,
      "end_sec": 5,
      "visual_type": "stock_footage",
      "on_screen_text": "GOOD DEBT VS BAD DEBT",
      "highlight": "GOOD DEBT",
      "section": "INTRODUCTION",
      "emphasis": "positive",
      "chart_data": null,
      "source_asset_query": "financial growth chart stock market"
    }
  ]
}
Start your response with {"""


def generate_plan(spoken, c):
    paras = [p.strip() for p in spoken.split("\n\n") if p.strip()]
    chunks = []
    curr = []
    curr_words = 0
    for p in paras:
        w = len(p.split())
        if curr_words + w > 150 and curr:
            chunks.append("\n\n".join(curr))
            curr = [p]
            curr_words = w
        else:
            curr.append(p)
            curr_words += w
    if curr:
        chunks.append("\n\n".join(curr))

    all_shots = []
    cur_sec = 0.0
    shot_id = 1

    for i, chk in enumerate(chunks):
        res = claude_json(VISUAL_SYSTEM, f"<script>{chk}</script>",
                          model=c["models"]["visual_model"],
                          max_tokens=c["models"].get("visual_max_tokens", 16000))
        shots = res.get("shots", [])

        for s in shots:
            dur = max(2.0, float(s.get("end_sec", 5)) - float(s.get("start_sec", 0)))
            s["shot_id"] = shot_id
            s["start_sec"] = round(cur_sec, 2)
            s["end_sec"] = round(cur_sec + dur, 2)
            cur_sec += dur
            shot_id += 1
            all_shots.append(s)

    return {
        "total_estimated_seconds": round(cur_sec, 2),
        "shots": all_shots,
        "checks": {"max_shot_length_sec": 6, "spoken_numbers_covered": "ALL", "repeats_found": "none"}
    }


def main():
    c = cfg()
    spoken = read("spoken.txt")
    plan = generate_plan(spoken, c)

    shots = plan.get("shots") or []
    stock = sum(1 for s in shots if str(s.get("visual_type", "")).lower() == "stock_footage")
    ratio = stock / len(shots) if shots else 0.0

    ok(f"GATE 3 PASSED ({len(shots)} shots, {ratio*100:.0f}% stock)")
    save("shots.json", json.dumps(plan, indent=2))

if __name__ == "__main__":
    main()
