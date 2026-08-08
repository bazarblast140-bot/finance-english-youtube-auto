import json
import os
import sys
import requests
from pathlib import Path

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

def claude_json(system_prompt, user_prompt, model="kimi-k3", max_tokens=4096):
    """Call LLM API (Moonshot Kimi K3 or Anthropic) and parse JSON output."""
    moonshot_key = os.environ.get("MOONSHOT_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if moonshot_key:
        url = "https://api.moonshot.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {moonshot_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model if model and "kimi" in model else "kimi-k3",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3
        }
        r = requests.post(url, headers=headers, json=payload, timeout=120)
        if r.status_code != 200:
            die(f"Moonshot API error {r.status_code}: {r.text[:300]}")
        res_data = r.json()
        content = res_data["choices"][0]["message"]["content"]
        return json.loads(content)
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
        if r.status_code != 200:
            die(f"Anthropic API error {r.status_code}: {r.text[:300]}")
        res_data = r.json()
        content = res_data["content"][0]["text"]
        return json.loads(content)
    else:
        die("Missing API Key! Please set MOONSHOT_API_KEY or ANTHROPIC_API_KEY in environment/secrets.")
