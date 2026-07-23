"""Stage 6: Final Verify Gate. Runs the verify agent over the finished pipeline outputs
and writes a Hinglish report (run/report.md) for Rajesh. This is the report you read."""
import json
from common import cfg, claude, read, save, ok, RUN

FINAL_SYSTEM = """You are the Main Verify Agent doing the FINAL GATE on a finished faceless finance video, then writing a report for Rajesh in HINGLISH.

Re-check the three critical nodes one last time using the provided artifacts:
1. Facts: is every figure in the FACT LEDGER sourced (not UNVERIFIED)?
2. Compliance: no fake-expert persona, disclaimer present, educational (not advice) framing?
3. Subtitles: were subtitles generated? (assume yes if a subs file was produced — stated below.)

Then surface JUDGMENT calls the human must decide (thumbnail appeal, "is this boring?", any assumption like an illustrative return rate).

Write the report in this exact Hinglish format, answer-first, mobile-readable:

VERDICT: [READY TO PUBLISH] / [NEEDS FIX — X items]

✅ Auto-checks pass:
<one line: Hook | Facts | Compliance | Coverage | Visuals | Length>

⚠️ Tumhe dekhna hai (judgment calls):
- <thumbnail note>
- <any assumption/taste concern with timestamp>

🔴 Risks / assumptions:
- <claims marked Likely/Assuming, jurisdiction notes>

FAILS this round: <none | list>

Keep it short. No preamble before VERDICT."""

def main():
    c = cfg()
    script = read("script.txt")
    shots = json.loads(read("shots.json"))
    subs_made = (RUN / "subs.srt").exists()
    video_made = (RUN / "final.mp4").exists()

    user = f"""<artifacts>
<script_with_fact_ledger>
{script}
</script_with_fact_ledger>
<visual_checks>{json.dumps(shots.get('checks', {}))}</visual_checks>
<subtitles_generated>{subs_made}</subtitles_generated>
<video_built>{video_made}</video_built>
</artifacts>
Write the final Hinglish report."""

    report = claude(FINAL_SYSTEM, user, model=c["models"]["verify_model"], max_tokens=1500)
    save("report.md", report)
    print("\n" + "=" * 50 + "\n" + report + "\n" + "=" * 50)
    ok("wrote run/report.md")

if __name__ == "__main__":
    main()
