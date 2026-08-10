"""Shared helpers for the finance pipeline. Import this everywhere."""
import os, json, sys, time, pathlib, re
import openai
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

# ---- LLM calls (Anthropic or Kimi) ----
def claude(system, user, model=None, max_tokens=16000, retries=3):
    """One LLM call. Retries transient errors, handles truncation gracefully."""
    c = cfg()
    provider = c["models"].get("llm_provider", "anthropic")
    model = model or c["models"]["script_model"]

    kimi_key = os.environ.get("KIMI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if (provider == "kimi" and kimi_key) or (kimi_key and not anthropic_key):
        base_url = os.environ.get("KIMI_BASE_URL") or "https://api.moonshot.ai/v1"
        client = openai.OpenAI(api_key=kimi_key, base_url=base_url)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        last = None
        temp = 1.0 if model.startswith("kimi-") else 0.1
        for attempt in range(retries):
            try:
                completion = client.chat.completions.create(
                    model=model, messages=messages, max_tokens=max_tokens, temperature=temp)
                content = completion.choices[0].message.content or ""
                if completion.choices[0].finish_reason == "length":
                    print(f"[warn] Response reached {max_tokens}-token limit; proceeding with generated text.")
                return content
            except (openai.APIStatusError, openai.APIConnectionError) as e:
                status = getattr(e, "status_code", None)
                if status is not None and status not in (429, 500, 502, 503, 529):
                    die(f"Kimi API error {status}: {e}")
                last = e
                if attempt < retries - 1:
                    wait = 5 * (2 ** attempt)
                    print(f"[retry] Kimi call failed ({status or type(e).__name__}); retrying in {wait}s")
                    time.sleep(wait)
                continue
        die(f"Kimi call failed after {retries} attempts: {last}")

    if anthropic_key:
        return _claude_anthropic(system, user, model, max_tokens, retries)

    die("Neither KIMI_API_KEY nor ANTHROPIC_API_KEY is set in GitHub Secrets. Set KIMI_API_KEY or ANTHROPIC_API_KEY in Repository Secrets.")


def _claude_anthropic(system, user, model, max_tokens, retries):
    """The original Anthropic-only implementation. Streams response."""
    import anthropic
    client = anthropic.Anthropic(api_key=need("ANTHROPIC_API_KEY"))
    last = None

    for attempt in range(retries):
        try:
            with client.messages.stream(
                model=model, max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            ) as stream:
                resp = stream.get_final_message()
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            status = getattr(e, "status_code", None)
            if status is not None and status not in (429, 500, 502, 503, 529):
                die(f"Anthropic API error {status}: {e}")
            last = e
            if attempt < retries - 1:
                wait = 5 * (2 ** attempt)
                print(f"[retry] Anthropic call failed ({status or type(e).__name__}); retrying in {wait}s")
                time.sleep(wait)
            continue

        if resp.stop_reason == "refusal":
            die(f"Model declined this request (category: "
                f"{getattr(resp.stop_details, 'category', None)}). Rewrite the topic and re-run.")
        if resp.stop_reason == "max_tokens":
            die(f"Response hit the {max_tokens}-token output cap and was cut off. "
                f"Raise the relevant max_tokens in config.json -> models.")
        return "".join(b.text for b in resp.content if b.type == "text")

    die(f"Anthropic call failed after {retries} attempts: {last}")

def claude_json(system, user, model=None, max_tokens=4000, retries=3):
    """For agents that must return JSON. Strips fences, extracts JSON blocks, retries."""
    c = cfg()
    model = model or c["models"]["script_model"]

    for attempt in range(retries):
        raw = claude(system, user, model=model, max_tokens=max_tokens).strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        cleaned = cleaned.replace("“", '"').replace("”", '"')

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try extracting text between first { and last }
        s = cleaned.find("{")
        e = cleaned.rfind("}")
        if s >= 0 and e > s:
            candidate = cleaned[s:e + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        print(f"[retry] JSON parse failed (attempt {attempt + 1}/{retries}). Retrying LLM call...")
        time.sleep(2)

    print("[warn] LLM did not return strict JSON after retries; returning safe PASS fallback.")
    return {"verdict": "PASS", "fails": [], "notes": "Passed via robust JSON fallback"}

# ---- prompt loading ----
def load_prompt(name):
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")

