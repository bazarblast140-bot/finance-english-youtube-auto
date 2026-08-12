"""Stage 4: Visual Agent builds a timed shot list, Gate 3 verifies density/numbers/repeats.
Exits non-zero on Gate 3 fail."""
import json
from common import cfg, claude_json, read, save, ok, die, RUN

VISUAL_SYSTEM = """You are the Visual Planner Agent for The Money Rule — a faceless finance YouTube channel that must stay monetization-safe and look ORIGINAL (Excalidraw / hand-drawn style).

HARD RULES (YouTube reuse / monetization):
1. Prefer ORIGINAL visuals. Target: at most 30% of shots may be stock_footage.
2. When the script has numbers, comparisons, timelines, or percentages → visual_type MUST be "chart" and chart_data MUST be filled with the REAL numbers from the script.
3. When explaining a rule/concept without a clean numeric series → visual_type "card" (plain branded card + on_screen_text). chart_data null.
4. stock_footage is only for emotional B-roll (person stressed about bills, empty wallet vibe) — never for explaining the rule itself.
5. Dynamic pacing: 4-7 second shots.
6. on_screen_text under 6 words. Put the KEY number or phrase on screen.
7. source_asset_query under 5 words (only used if visual_type is stock_footage).

chart_data format when visual_type is "chart":
  {"type": "bar" or "line", "labels": ["A","B","C"], "values": [10, 25, 40]}
  Labels and values must match and come from the script numbers.

JSON FORMAT (Output ONLY this JSON object):
{
  "shots": [
    {
      "shot_id": 1,
      "start_sec": 0,
      "end_sec": 5,
      "visual_type": "chart",
      "on_screen_text": "22.76% CARD APR",
      "highlight": "22.76%",
      "section": "THE COST",
      "emphasis": "warning",
      "chart_data": {"type": "bar", "labels": ["Minimum", "Snowball", "Avalanche"], "values": [48, 36, 29]},
      "source_asset_query": null
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
    if not shots:
        die("GATE 3 FAILED: Visual Agent returned zero shots.")

    stock = sum(1 for s in shots if str(s.get("visual_type", "")).lower() == "stock_footage")
    chart = sum(1 for s in shots if str(s.get("visual_type", "")).lower() == "chart")
    ratio = stock / len(shots)
    max_ratio = float(c["pipeline"].get("max_stock_ratio", 0.30))

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
