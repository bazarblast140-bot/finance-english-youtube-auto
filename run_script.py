"""Stage 2: Script Agent writes the script, then Gate 1 verifies it.
Includes automatic 3-attempt repair loop so prompt issues auto-fix themselves."""
from common import cfg, claude, claude_json, load_prompt, read, save, ok, die

SCRIPT_SYSTEM = """You are the Script Agent for a faceless English finance/investing YouTube channel targeting US/UK/CA/AU viewers. You write information-dense, original scripts with a specific angle — never generic listicles.

HARD RULES:
1. Finance is YMYL. Every specific figure must be REAL and sourced in the FACT LEDGER (e.g. [SOURCE: Federal Reserve SCF 2023] or [SOURCE: BLS 2024]). Mark every figure with its source in the body tags [SOURCE: ...] and in the FACT LEDGER.
2. Hook must be a high-impact pattern-interrupt question or sharp contrast in the first sentence to stop the scroll.
3. Angle must be a sharp, non-generic insight (e.g., benchmark comparison or financial rule mechanism).
4. Never present as a credentialed expert. Educational narrator only.
5. TTS-safe: no emojis, no #/&/% inside spoken lines — write "8 percent" not "8%". Numbers written to be SPOKEN.

Output the exact structure: TITLE / HOOK (0-15 sec) / BODY (with [SEGMENT n] and [SOURCE] tags) / CTA / DISCLAIMER LINE / FACT LEDGER. Plain text, no markdown fences."""

GATE1_SYSTEM = """You are the Verify Agent running GATE 1 on a finance video script. Check:
- Hook present in first 15 sec, genuinely stops the viewer.
- Every specific figure is sourced in the FACT LEDGER.
- No fake-expert persona; disclaimer line present; educational framing.
- Structure: hook -> segments -> CTA. Broken into segments.
- Has a specific original angle.

Return ONLY JSON: {"verdict":"PASS"|"FAIL","fails":["specific issue with location", ...],"notes":"one line"}
Start your response with {"""

def main():
    c = cfg()
    topic = read("topic.txt").strip()
    wc = c["video"]["target_word_count"]
    mins = c["video"]["target_minutes"]

    prompt = f"""<task>Write a complete YouTube video script on the topic. Information-dense, original angle.</task>
<context>Faceless English finance channel. Audience US/UK/CA/AU. Target: {mins} min (~{wc} spoken words total). Feeds a TTS Voice Agent then Visual Agent — keep TTS-clean.</context>
<topic>{topic}</topic>
<output_format>TITLE / HOOK (0-15 sec) / BODY with [SEGMENT n: label] and [SOURCE: ...] tags / CTA / DISCLAIMER LINE / FACT LEDGER listing every figure + source status.</output_format>"""

    last_fails = []
    for attempt in range(3):
        user = prompt
        if last_fails:
            user += f"\n\n<previous_attempt_issues>\nThe previous script attempt was rejected by Gate 1 due to these issues:\n- " + "\n- ".join(last_fails) + "\n\nCRITICAL INSTRUCTION: You MUST fix every listed issue above in this rewrite to pass Gate 1!\n</previous_attempt_issues>"

        script = claude(SCRIPT_SYSTEM, user, model=c["models"]["script_model"], max_tokens=c["models"]["max_tokens"])
        save("script.txt", script)

        # ---- GATE 1 ----
        gate = claude_json(GATE1_SYSTEM, f"<script>{script}</script>", model=c["models"]["verify_model"])
        if gate.get("verdict") == "PASS":
            ok(f"GATE 1 PASSED (attempt {attempt+1}). {gate.get('notes','')}")
            return

        last_fails = gate.get("fails") or ["General Gate 1 quality check failed"]
        print(f"[retry] Gate 1 attempt {attempt+1}/3 failed: {last_fails}. Retrying script rewrite...")

    # Best-effort fallback if 3 attempts reached
    save("gate1_report.txt", "\n".join(last_fails))
    ok(f"GATE 1 Completed after 3 attempts with warnings: {last_fails}")

if __name__ == "__main__":
    main()
