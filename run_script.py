"""Stage 2: Script Agent writes the script, then Gate 1 verifies it.
Exits non-zero if Gate 1 fails (pipeline stops)."""
from common import cfg, claude, claude_json, load_prompt, read, save, ok, die

SCRIPT_SYSTEM = """You are the Script Agent for a faceless English finance/investing YouTube channel targeting US/UK/CA/AU viewers. You write information-dense, original scripts with a specific angle — never generic listicles.

HARD RULES:
1. Finance is YMYL. Every specific figure must be REAL and sourced. If you cannot source a figure, mark it [UNVERIFIED: needs source] — do not invent.
2. Never present as a credentialed expert. Educational narrator only.
3. Never give personalized advice. "One common approach is..." not "you should buy...".
4. TTS-safe: no emojis, no #/&/% inside spoken lines — write "8 percent" not "8%". Numbers written to be SPOKEN.

Output the exact structure: TITLE / HOOK (0-15 sec) / BODY (with [SEGMENT n] and [SOURCE] tags) / CTA / DISCLAIMER LINE / FACT LEDGER. Plain text, no markdown fences."""

GATE1_SYSTEM = """You are the Verify Agent running GATE 1 on a finance video script. Check ALL:
- Hook present in first 15 sec, genuinely stops the viewer.
- Every specific figure is sourced in the FACT LEDGER or marked UNVERIFIED. ANY unsourced figure = FAIL.
- No fake-expert persona; disclaimer line present; educational (not advice) framing.
- Structure: hook -> segments -> CTA. Broken into segments.
- Has a specific original angle, not a generic listicle.

Return ONLY JSON: {"verdict":"PASS"|"FAIL","fails":["specific issue with location", ...],"notes":"one line"}
Start your response with {"""

def main():
    c = cfg()
    topic = read("topic.txt").strip()
    wc = c["video"]["target_word_count"]
    mins = c["video"]["target_minutes"]

    user = f"""<task>Write a complete YouTube video script on the topic. Information-dense, original angle.</task>
<context>Faceless English finance channel. Audience US/UK/CA/AU. Target: {mins} min (~{wc} words). Feeds a TTS Voice Agent then Visual Agent — keep TTS-clean.</context>
<topic>{topic}</topic>
<output_format>TITLE / HOOK (0-15 sec) / BODY with [SEGMENT n: label] and [SOURCE: ...] tags / CTA / DISCLAIMER LINE / FACT LEDGER listing every figure + source status.</output_format>"""

    script = claude(SCRIPT_SYSTEM, user, model=c["models"]["script_model"], max_tokens=c["models"]["max_tokens"])
    save("script.txt", script)

    # ---- GATE 1 ----
    gate = claude_json(GATE1_SYSTEM, f"<script>{script}</script>", model=c["models"]["verify_model"])
    if gate["verdict"] != "PASS":
        save("gate1_report.txt", "\n".join(gate.get("fails", [])))
        die(f"GATE 1 FAILED: {gate.get('fails')}")
    ok(f"GATE 1 PASSED. {gate.get('notes','')}")

if __name__ == "__main__":
    main()
