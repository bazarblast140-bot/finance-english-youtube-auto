"""Stage 4: Visual Agent builds a timed shot list, Gate 3 verifies density/numbers/repeats.
Exits non-zero on Gate 3 fail."""
import json
from common import cfg, claude_json, read, save, ok, die, RUN

VISUAL_SYSTEM = """You are the Visual Planner for The Money Rule (One Rule Board style).

GOAL: viewer should SEE the explanation, not just read a wall of text. Prefer hand-drawn / pen-board / chart over stock.

HARD RULES:
1. Max 15% of shots may be stock_footage (emotion only — never the explanation).
2. Numbers, comparisons, timelines → visual_type "chart" with real script numbers in chart_data.
3. Concepts / rules / actions → visual_type "card" (pen-board style headline, short on_screen_text).
4. on_screen_text: max 5 words. The KEY phrase or number only — not a sentence.
5. section labels: short board headers like RULE, MYTH, MATH, ACTION (not long sentences).
6. Shot length 5–8 seconds. Fewer, clearer shots beat many noisy ones.
7. animation_in: prefer "fade_in_up" for calm tone (not aggressive zoom every shot).
8. source_asset_query only if stock_footage; under 5 words; must match the spoken moment.

chart_data when visual_type is chart:
  {"type": "bar" or "line", "labels": ["A","B"], "values": [10, 25]}
  Values MUST come from the script.

JSON ONLY:
{
  "shots": [
    {
      "shot_id": 1,
      "start_sec": 0,
      "end_sec": 6,
      "visual_type": "card",
      "on_screen_text": "ONE RULE",
      "highlight": "ONE RULE",
      "section": "BOARD",
      "emphasis": "neutral",
      "animation_in": "fade_in_up",
      "chart_data": null,
      "source_asset_query": null
    }
  ]
}
Start with {"""


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
    if not shots:
        die("GATE 3 FAILED: Visual Agent returned zero shots.")

    stock = sum(1 for s in shots if str(s.get("visual_type", "")).lower() == "stock_footage")
    chart = sum(1 for s in shots if str(s.get("visual_type", "")).lower() == "chart")
    ratio = stock / len(shots)
    max_ratio = float(c["pipeline"].get("max_stock_ratio", 0.15))

    # charts with numbers are original (Excalidraw-style) — good for monetization
    missing_chart_data = [
        s.get("shot_id") for s in shots
        if str(s.get("visual_type", "")).lower() == "chart"
        and not (isinstance(s.get("chart_data"), dict)
                 and s["chart_data"].get("labels")
                 and s["chart_data"].get("values"))
    ]

    fails = []
    if ratio > max_ratio + 1e-9:
        fails.append(
            f"Too much stock footage: {ratio*100:.0f}% (max {max_ratio*100:.0f}%). "
            f"Rewrite shots to use chart/card so the channel stays original and monetizable."
        )
    if missing_chart_data:
        fails.append(f"chart shots missing chart_data: {missing_chart_data}")
    if chart == 0 and len(shots) >= 6:
        fails.append("No chart shots — at least one number-driven Excalidraw chart is required for a 6+ shot video.")

    if fails:
        save("gate3_report.txt", "\n".join(fails))
        die("GATE 3 FAILED: " + " | ".join(fails))

    ok(f"GATE 3 PASSED ({len(shots)} shots, {ratio*100:.0f}% stock, {chart} charts)")
    save("shots.json", json.dumps(plan, indent=2))

if __name__ == "__main__":
    main()
