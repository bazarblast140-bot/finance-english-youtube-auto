"""Stage 2: Script Agent writes the script, local Gate 1 verifies structure.
Gate 1 is now a fast local Python check (no LLM call) — saves credits.
Max 2 attempts: generate → local check → (if fail) regenerate with fix notes → done."""
import re
from common import cfg, claude, read, save, ok, die

SCRIPT_SYSTEM = """You are the Script Agent for The Money Rule — English finance channel (US/UK/CA/AU).

VISUAL STYLE TO WRITE FOR (Wealth-Logic-style explainer):
- One fixed cartoon host (man in white lab coat) points at icons, numbers, and charts.
- Clean white background. Big on-screen numbers. Simple icons (car, loan paper, calendar, arrow).
- One idea per 5–8 second beat. Name the trap/rule in a title card.

Your job: make ONE money rule or trap so clear a busy person gets it in under 5 minutes.

STRUCTURE (follow exactly):
TITLE:
<Searchable. Prefer form: "The _____ Trap" or "The _____ Rule" + benefit. Specific, not "X Explained".>

HOOK (0-12 sec):
<Pattern-interrupt. First sentence stops the scroll. No throat-clearing.>

BODY:
[SEGMENT 1: TITLE CARD]
<Name the trap/rule in spoken form, e.g. "This is the rolling car trap." One sharp setup line.>

[SEGMENT 2: THE HARD NUMBER]
<ONE concrete number with [SOURCE: ...]. Example a viewer can picture. This number will appear huge on screen.>

[SEGMENT 3: HOW THE TRAP WORKS]
<Mechanism in plain English. Walk a simple timeline or loop (year 1 → year 3 → again). Short sentences.>

[SEGMENT 4: WHAT MOST PEOPLE ACTUALLY DO]
<The common mistake. One vivid picture. Calm, not preachy.>

[SEGMENT 5: THE ONE ACTION]
<Exactly one thing to do this week. Specific.>

CTA:
<One calm line. e.g. "If this rule helped, the next video covers the exception.">

DISCLAIMER LINE:
<One spoken sentence: educational only, not financial advice.>

FACT LEDGER:
<- each figure → source>

HARD RULES:
1. YMYL: put at least THREE [SOURCE: ...] tags in the BODY (not only in FACT LEDGER). Example: [SOURCE: Federal Reserve 2024].
2. FACT LEDGER must list every figure with its source line.
3. Must include sections exactly named: CTA:  and  DISCLAIMER LINE:  and  FACT LEDGER:
4. TTS-safe: write "eight percent" not "8%"; no emojis, no #/& inside spoken lines.
5. Spoken length: 550–750 words total (about 4–5 minutes). Dense, not padded.
6. Forbidden filler: "in this video", "without further ado", "let's dive in", "game changer", "in today's video", "so basically".
7. Narrator = calm teacher (lab expert), not hype. Short sentences. One idea per sentence.
8. Prefer one vivid example over three vague tips.

Output plain text only — no markdown fences."""


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

    prompt = f"""<task>Write a One Rule Board script: one rule, clear mechanism, one action. Explain — do not pad.</task>
<context>Channel: The Money Rule. Audience US/UK/CA/AU beginners. Target ~{mins} min ({wc} spoken words ±25%). Calm teacher voice. TTS-clean. No filler phrases.</context>
<topic>{topic}</topic>
<must_include>
- At least 3 separate [SOURCE: ...] tags inside the spoken BODY
- Sections: CTA: / DISCLAIMER LINE: / FACT LEDGER:
- At least 3 [SEGMENT n: ...] blocks
- Spoken body at least {int(wc*0.75)} words before FACT LEDGER
</must_include>
<output_format>TITLE / HOOK (0-12 sec) / BODY with [SEGMENT 1-5] as defined in system / CTA / DISCLAIMER LINE / FACT LEDGER</output_format>"""

    last_fails = []
    model = c["models"]["script_model"]
    max_tok = c["models"].get("script_max_tokens", 4000)
    print(f"[info] Script Agent: model={model}, max_tokens={max_tok}, topic='{topic}'")

    for attempt in range(3):  # max 3 attempts
        user = prompt
        if last_fails:
            user += f"\n\n<previous_attempt_issues>\nThe previous script was rejected by automated checks due to these structural issues:\n- " + "\n- ".join(last_fails) + "\n\nYou MUST fix every listed issue in this rewrite.\n</previous_attempt_issues>"

        print(f"[info] Attempt {attempt+1}/3: calling LLM...")
        script = claude(SCRIPT_SYSTEM, user, model=model, max_tokens=max_tok)
        save("script.txt", script)
        print(f"[info] Script generated: {len(script)} chars, ~{len(script.split())} words")

        # ---- GATE 1 (local, no LLM call, zero credits) ----
        passed, fails = gate1_local(script, c)
        if passed:
            ok(f"GATE 1 PASSED (attempt {attempt+1}, local check). Structure verified.")
            return

        last_fails = fails
        print(f"[retry] Gate 1 local check attempt {attempt+1}/3 failed: {fails}")

    # All attempts exhausted — STOP the pipeline (don't waste credits downstream)
    save("gate1_report.txt", "\n".join(last_fails))
    die(f"GATE 1 FAILED after 3 attempts. Issues: {last_fails}")

if __name__ == "__main__":
    main()
