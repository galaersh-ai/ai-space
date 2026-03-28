#!/usr/bin/env python3
import os, json, requests
from pathlib import Path

AI_HOME = Path("/root/ai_space")
OUTBOX = AI_HOME / "outbox" / "messages.json"

# Load .env FIRST
env_file = AI_HOME / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

TG_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT_ID", "")

def publish():
    if not OUTBOX.exists():
        print("No outbox file")
        return
    
    messages = json.loads(OUTBOX.read_text())
    print(f"Messages: {len(messages)}")
    
    for msg in messages:
        session = msg.get("session", "?")
        text = msg.get("content", "")
        if text:
            full_text = f"[Session {session}] {text}"
            print(f"Sending: {full_text[:50]}...")
            resp = requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": TG_CHAT, "text": full_text}
            )
            print(f"Response: {resp.json()}")
    
    OUTBOX.write_text("[]")
    print("Cleared outbox")

if __name__ == "__main__":
    publish()
