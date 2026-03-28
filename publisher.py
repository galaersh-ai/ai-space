#!/usr/bin/env python3
import os, json, requests
from pathlib import Path

AI_HOME = Path("/root/ai_space")
OUTBOX = AI_HOME / "outbox" / "messages.json"

# Read from .env
TG_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT_ID", "")

def publish():
    if not OUTBOX.exists(): return
    messages = json.loads(OUTBOX.read_text())
    for msg in messages:
        session = msg.get("session", "?")
        text = msg.get("content", "")
        if text:
            full_text = f"[Session {session}] {text}"
            requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": TG_CHAT, "text": full_text}
            )
    OUTBOX.write_text("[]")

if __name__ == "__main__":
    # Load .env
    env_file = AI_HOME / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                os.environ.setdefault(k, v)
    publish()
