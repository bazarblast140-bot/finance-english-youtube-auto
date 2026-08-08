import json, os, re, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).parent.resolve()
RUN = ROOT / "run"

def cfg():
    path = ROOT / "config.json"
    if not path.exists():
        die("config.json missing")
    return json.loads(path.read_text(encoding="utf-8"))

def read(filename):
    p = RUN / filename
    if not p.exists():
        die(f"run/{filename} missing")
    return p.read_text(encoding="utf-8")

def save(filename, content):
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / filename).write_text(content, encoding="utf-8")

def need(env_var):
    val = os.environ.get(env_var, "").strip()
    if not val:
        die(f"Missing required environment variable: {env_var}")
    return val

def ok(msg):
    print(f"[OK] {msg}")

def die(msg):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)

def claude_json(system_prompt, user_prompt, model=None, max_tokens=4096):
    c = cfg()
    model = model or c["models"].get("script_model", "kimi-k3")
    
    moonshot_key = os.environ.get("MOONSHOT_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if moonshot_key:
        url = "https://api.moonshot.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {moonshot_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "kimi-k3",
            "messages": [
                {"role": "system", "content": system_prompt + "\nIMPORTANT: Return ONLY valid JSON."},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"}
        }
        for attempt in range(3):
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=120)
                if r.status_code == 200:
                    content = r.json()["choices"][0]["message"]["content"]
                    match = re.search(r"\{.*\}", content, re.DOTALL)
                    if match:
                        return json.loads(match.group(0))
                    return json.loads(content)
                if r.status_code in (429, 500, 502, 503) and attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                die(f"Moonshot Kimi K3 API error {r.status_code}: {r.text[:300]}")
            except Exception as e:
                if attempt == 2:
                    die(f"Moonshot API request failed: {e}")
                time.sleep(3)

    elif anthropic_key:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": anthropic_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}]
        }
        r = requests.post(url, headers=headers, json=payload, timeout=120)
        if r.status_code == 200:
            text = r.json()["content"][0]["text"]
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return json.loads(text)
        die(f"Anthropic API error {r.status_code}: {r.text[:300]}")
    else:
        die("Neither MOONSHOT_API_KEY nor ANTHROPIC_API_KEY is set in environment!")
