#!/usr/bin/env python3
import os, json, requests
from pathlib import Path

AI_HOME = Path("/root/ai_space")
LOGS_DIR = AI_HOME / "logs"

# Read from .env
TG_TOKEN = os.environ.get("TG_SYSTEM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT_ID", "")

def send_system_message(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": f"🔧 System: {text}", "parse_mode": "Markdown"}
        )
    except: pass

def analyze_logs():
    log_files = sorted(LOGS_DIR.glob("api/session_*_output.json"), reverse=True)
    if not log_files: return
    
    last = log_files[0]
    data = json.loads(last.read_text())
    usage = data.get("usage", {})
    session = last.stem.split("_")[1]
    
    msg = f"""📊 Session #{session}

**Tokens:** {usage.get('prompt_tokens', 0)} prompt + {usage.get('completion_tokens', 0)} completion
**Total:** {usage.get('total_tokens', 0)}"""
    
    send_system_message(msg)

if __name__ == "__main__":
    env_file = AI_HOME / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                os.environ.setdefault(k, v)
    analyze_logs()
