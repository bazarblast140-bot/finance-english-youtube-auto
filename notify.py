"""Sends the verify report to Telegram. Called at the end of every run.

Degrades gracefully: if Telegram isn't configured, the report still prints to the
console. A missing notification must never look like a failed video.
"""
import os, sys, requests
from common import read, RUN, ok

def send(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[skip] Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID). "
              "Report printed above only.")
        return False
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text[:4000]}, timeout=30)
    r.raise_for_status()
    return True

def main():
    status = "success"
    if "--status" in sys.argv:
        status = sys.argv[sys.argv.index("--status") + 1]

    if (RUN / "report.md").exists():
        body = read("report.md")
    else:
        body = (f"Run finished with status: {status}. No report generated — a gate likely "
                f"failed. Check the console output or the run/ artifacts.")

    message = "🎬 Daily Finance Video\n\n" + body
    try:
        if send(message):
            ok("notified on Telegram")
    except requests.RequestException as e:
        # never fail the pipeline over a notification
        print(f"[warn] Telegram send failed: {e}")

if __name__ == "__main__":
    main()
