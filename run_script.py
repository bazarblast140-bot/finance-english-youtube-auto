"""Stage 2: Script Agent writes the script, local Gate 1 verifies structure.
Gate 1 is now a fast local Python check (no LLM call) — saves credits.
Max 2 attempts: generate → local check → (if fail) regenerate with fix notes → done."""
import re
from common import cfg, claude, read, save, ok, die

SCRIPT_SYSTEM = """You are the Script Agent for a faceless English finance/investing YouTube channel targeting US/UK/CA/AU viewers. You write information-dense, original scripts with a specific angle — never generic listicles.

HARD RULES:
1. Finance is YMYL. Every specific figure must be REAL and sourced in the FACT LEDGER (e.g. [SOURCE: Federal Reserve SCF 2023] or [SOURCE: BLS 2024]). Mark every figure with its source in the body tags [SOURCE: ...] and in the FACT LEDGER.
2. Hook must be a high-impact pattern-interrupt question or sharp contrast in the first sentence to stop the scroll. Examples of GOOD hooks:
   - "What if the most popular investing rule was built for 1982, not 2025?"
   - "There is a hidden 400 thousand dollar tax most people pay without realizing it."
   - "The average American retires with 65 percent less than they need — and the fix takes ten minutes."
   Do NOT write flat, self-evident statements like "Net worth shows true financial health" — those are NOT hooks.
3. Angle must be a sharp, non-generic insight (e.g., benchmark comparison, financial rule mechanism, myth vs data reality). "X explained" or "X 101" is NOT an angle — an angle is a CLAIM or REVELATION that makes the viewer rethink something.
4. Never present as a credentialed expert. Educational narrator only.
5. TTS-safe: no emojis, no #/&/% inside spoken lines — write "8 percent" not "8%". Numbers written to be SPOKEN.
6. Body must have at least 3 [SEGMENT n: label] sections with substantive content in each.
7. Every segment that mentions a specific number MUST have a [SOURCE: ...] tag.

QUALITY BAR (your script must pass ALL of these or it will be rejected):
- TITLE line present
- HOOK section present (first 15 seconds) with a genuine pattern-interrupt
- BODY with at least 3 [SEGMENT] tags
- At least 3 [SOURCE: ...] tags in the body
- CTA section present
- DISCLAIMER LINE present
- FACT LEDGER section present listing every sourced figure
- Total spoken words between 450 and 1050

Output the exact structure: TITLE / HOOK (0-15 sec) / BODY (with [SEGMENT n: label] and [SOURCE: ...] tags) / CTA / DISCLAIMER LINE / FACT LEDGER. Plain text, no markdown fences."""


def gate1_local(script, c):
    """Local Gate 1: checks script structure without any LLM call.
    Returns (pass: bool, fails: list[str])."""
    fails = []
    upper = script.upper()

    # Structure checks
    if "TITLE" not in upper[:200]:
        fails.append("Missing TITLE section at the start")

    if "HOOK" not in upper[:500]:
        fails.append("Missing HOOK section")

    segments = re.findall(r"\[SEGMENT\s+\d+", script, re.IGNORECASE)
    if len(segments) < 3:
        fails.append(f"Only {len(segments)} [SEGMENT] tags found (need at least 3)")

    sources = re.findall(r"\[SOURCE:", script, re.IGNORECASE)
    if len(sources) < 3:
        fails.append(f"Only {len(sources)} [SOURCE:] tags found (need at least 3)")

    if "CTA" not in upper:
        fails.append("Missing CTA section")

    if "DISCLAIMER" not in upper:
        fails.append("Missing DISCLAIMER LINE")

    if "FACT LEDGER" not in upper:
        fails.append("Missing FACT LEDGER section")

    # Word count check (approximate spoken words = everything before FACT LEDGER)
    body_end = script.upper().find("FACT LEDGER")
    spoken_part = script[:body_end] if body_end > 0 else script
    # Strip [SOURCE:...] and [SEGMENT...] tags for word count
    spoken_clean = re.sub(r"\[SOURCE:[^\]]*\]", "", spoken_part)
    spoken_clean = re.sub(r"\[SEGMENT[^\]]*\]", "", spoken_clean)
    spoken_clean = re.sub(r"\[UNVERIFIED[^\]]*\]", "", spoken_clean)
    words = len(spoken_clean.split())

    target = c["video"]["target_word_count"]
    tol = c["pipeline"].get("word_count_tolerance", 0.4)
    lo, hi = int(target * (1 - tol)), int(target * (1 + tol))
    if words < lo:
        fails.append(f"Script too short: ~{words} words (minimum {lo})")
    elif words > hi:
        fails.append(f"Script too long: ~{words} words (maximum {hi})")

    return len(fails) == 0, fails


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
    model = c["models"]["script_model"]
    max_tok = c["models"].get("script_max_tokens", 4000)
    print(f"[info] Script Agent: model={model}, max_tokens={max_tok}, topic='{topic}'")

    for attempt in range(2):  # max 2 attempts (was 3)
        user = prompt
        if last_fails:
            user += f"\n\n<previous_attempt_issues>\nThe previous script was rejected by automated checks due to these structural issues:\n- " + "\n- ".join(last_fails) + "\n\nYou MUST fix every listed issue in this rewrite.\n</previous_attempt_issues>"

        print(f"[info] Attempt {attempt+1}/2: calling LLM...")
        script = claude(SCRIPT_SYSTEM, user, model=model, max_tokens=max_tok)
        save("script.txt", script)
        print(f"[info] Script generated: {len(script)} chars, ~{len(script.split())} words")

        # ---- GATE 1 (local, no LLM call, zero credits) ----
        passed, fails = gate1_local(script, c)
        if passed:
            ok(f"GATE 1 PASSED (attempt {attempt+1}, local check). Structure verified.")
            return

        last_fails = fails
        print(f"[retry] Gate 1 local check attempt {attempt+1}/2 failed: {fails}")

    # All attempts exhausted — STOP the pipeline (don't waste credits downstream)
    save("gate1_report.txt", "\n".join(last_fails))
    die(f"GATE 1 FAILED after 2 attempts. Issues: {last_fails}")

if __name__ == "__main__":
    main()
