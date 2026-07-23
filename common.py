"""Shared helpers for the finance pipeline. Import this everywhere."""
import os, json, sys, time, pathlib
from datetime import datetime

ROOT = pathlib.Path(__file__).parent
RUN = ROOT / "run"
RUN.mkdir(exist_ok=True)

# Windows consoles default to cp1252 and blow up on the emojis in the verify
# report. Force UTF-8 on stdout/stderr so printing a report never crashes a run.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ---- env loading (simple .env parser, no extra deps) ----
def load_env():
    envf = ROOT / ".env"
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
load_env()

def cfg():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

def need(key):
    v = os.environ.get(key)
    if not v:
        die(f"Missing env var {key}. Set it in .env (see .env.example).")
    return v

def die(msg, code=1):
    print(f"[FAIL] {msg}", file=sys.stderr)
    sys.exit(code)

def ok(msg):
    print(f"[OK] {msg}")

def save(name, text):
    (RUN / name).write_text(text, encoding="utf-8")
    ok(f"wrote run/{name}")

def read(name):
    return (RUN / name).read_text(encoding="utf-8")

# ---- Anthropic call ----
def claude(system, user, model=None, max_tokens=4000, retries=3):
    """One Claude call. Retries on overload/rate-limit/transient API errors —
    a 529 shouldn't kill an 8-minute pipeline run."""
    import anthropic
    client = anthropic.Anthropic(api_key=need("ANTHROPIC_API_KEY"))
    model = model or cfg()["models"]["script_model"]
    last = None
    for attempt in range(retries):
        try:
            resp = client.messages.create(
                model=model, max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(b.text for b in resp.content if b.type == "text")
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            status = getattr(e, "status_code", None)
            if status is not None and status not in (429, 500, 502, 503, 529):
                die(f"Anthropic API error {status}: {e}")
            last = e
            if attempt < retries - 1:
                wait = 5 * (2 ** attempt)
                print(f"[retry] Anthropic call failed ({status or type(e).__name__}); retrying in {wait}s")
                time.sleep(wait)
    die(f"Anthropic call failed after {retries} attempts: {last}")

def claude_json(system, user, model=None, max_tokens=4000):
    """For agents that must return JSON. Strips fences, parses."""
    raw = claude(system, user, model, max_tokens)
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"Agent did not return valid JSON: {e}\n---\n{raw[:500]}")

# ---- prompt loading ----
def load_prompt(name):
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")
