#!/usr/bin/env python3
import os
import json
import requests
from pathlib import Path

AI_HOME = Path("/root/ai_space")
LOGS_DIR = AI_HOME / "logs"

# Load .env FIRST (before reading env vars)
env_file = AI_HOME / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

TG_TOKEN = os.environ.get("TG_SYSTEM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT_ID", "")


def send_system_message(text):
    if not TG_TOKEN or not TG_CHAT:
        print("Warning: TG_SYSTEM_BOT_TOKEN or TG_CHAT_ID not set")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": f"[System] {text}", "parse_mode": "Markdown"},
            timeout=10
        )
        return resp.ok
    except requests.RequestException as e:
        print(f"Failed to send system message: {e}")
        return False


def analyze_logs():
    log_files = sorted(LOGS_DIR.glob("api/session_*_output.json"), reverse=True)
    if not log_files:
        return

    last = log_files[0]
    try:
        data = json.loads(last.read_text())
    except json.JSONDecodeError as e:
        print(f"Failed to parse log file: {e}")
        return

    usage = data.get("usage", {})
    session = last.stem.split("_")[1]

    msg = f"""Session #{session}

*Tokens:* {usage.get('prompt_tokens', 0)} prompt + {usage.get('completion_tokens', 0)} completion
*Total:* {usage.get('total_tokens', 0)}"""

    send_system_message(msg)


if __name__ == "__main__":
    analyze_logs()
