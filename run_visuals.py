"""Stage 4: Visual Agent builds a timed shot list, Gate 3 verifies density/numbers/repeats.
Exits non-zero on Gate 3 fail."""
import json
from common import cfg, claude_json, read, save, ok, die, RUN

VISUAL_SYSTEM = """You are the Visual Planner Agent. Turn a finance script into a timed shot list for a faceless video. Every visual matches what the voice is saying.

RULES:
1. A NEW visual every 5-8 seconds. Never one image longer than 8 sec.
2. When a number is spoken, it MUST appear on screen (overlay or chart).
3. No visual repeats within the video.
4. Relevant visuals only. Prefer: clean charts for numbers > screen recordings > stock footage > AI image.

Assume ~150 spoken words per minute for timing.
Return ONLY JSON: {"total_estimated_seconds":N,"shots":[{"shot_id":1,"start_sec":0,"end_sec":6,"spoken_line":"...","visual_type":"chart|screen_recording|stock_footage|ai_image","visual_description":"...","on_screen_text":"... or null","source_asset_query":"..."}],"checks":{"max_shot_length_sec":N,"spoken_numbers_covered":"ALL on screen | list","repeats_found":"none | list"}}
Start your response with {"""

def main():
    c = cfg()
    spoken = read("spoken.txt")
    plan = claude_json(VISUAL_SYSTEM, f"<script>{spoken}</script>",
                       model=c["models"]["visual_model"],
                       max_tokens=c["models"].get("visual_max_tokens", 48000))

    # ---- GATE 3 ----
    ch = plan.get("checks", {})
    fails = []
    if ch.get("max_shot_length_sec", 99) > 8:
        fails.append(f"shot longer than 8s: {ch.get('max_shot_length_sec')}s")
    if "ALL" not in str(ch.get("spoken_numbers_covered", "")):
        fails.append(f"numbers missing on screen: {ch.get('spoken_numbers_covered')}")
    if ch.get("repeats_found", "none") != "none":
        fails.append(f"repeats: {ch.get('repeats_found')}")
    if fails:
        die(f"GATE 3 FAILED: {fails}")
    ok("GATE 3 PASSED (density, numbers, no repeats)")

    save("shots.json", json.dumps(plan, indent=2))

if __name__ == "__main__":
    main()
