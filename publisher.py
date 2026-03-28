#!/usr/bin/env python3
"""
publisher.py - Publish agent messages to Telegram

Reads messages from outbox/messages.json and sends to Telegram.
Features: retry logic, logging, error handling.
"""

import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path

AI_HOME = Path("/root/ai_space")
OUTBOX = AI_HOME / "outbox" / "messages.json"
LOGS_DIR = AI_HOME / "logs"
TELEGRAM_LOG = LOGS_DIR / "telegram.log"
ACTIONS_LOG = LOGS_DIR / "actions.log"

# Load .env
env_file = AI_HOME / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

TG_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT_ID", "")

# Config
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
MAX_MESSAGE_LENGTH = 4096  # Telegram limit


def log(msg):
    """Log to console and telegram.log"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TELEGRAM_LOG, "a") as f:
        f.write(line + "\n")


def log_action(action_type, details):
    """Log to actions.log (same format as core.py)"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": ts,
        "session": "publisher",
        "action": action_type,
        "details": details
    }
    with open(ACTIONS_LOG, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def check_config():
    """Verify Telegram configuration"""
    if not TG_TOKEN:
        log("ERROR: TG_BOT_TOKEN not set")
        return False
    if not TG_CHAT:
        log("ERROR: TG_CHAT_ID not set")
        return False
    return True


def send_message(text, retry=0):
    """Send message to Telegram with retry logic"""
    # Truncate if too long
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH - 20] + "\n\n... (truncated)"

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text},
            timeout=30
        )
        data = resp.json()

        if data.get("ok"):
            return True, data
        else:
            error = data.get("description", "Unknown error")
            # Retry on rate limit
            if resp.status_code == 429 and retry < MAX_RETRIES:
                retry_after = data.get("parameters", {}).get("retry_after", RETRY_DELAY)
                log(f"Rate limited, waiting {retry_after}s (retry {retry + 1}/{MAX_RETRIES})")
                time.sleep(retry_after)
                return send_message(text, retry + 1)
            return False, error

    except requests.RequestException as e:
        if retry < MAX_RETRIES:
            log(f"Request failed: {e}, retrying in {RETRY_DELAY}s ({retry + 1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
            return send_message(text, retry + 1)
        return False, str(e)


def publish():
    """Main publish function"""
    log("=== Publisher started ===")

    # Check config
    if not check_config():
        log_action("TG_CONFIG_ERROR", {"error": "Missing TG_BOT_TOKEN or TG_CHAT_ID"})
        return False

    # Check outbox
    if not OUTBOX.exists():
        log("No outbox file")
        return True

    try:
        messages = json.loads(OUTBOX.read_text())
    except json.JSONDecodeError as e:
        log(f"Invalid JSON in outbox: {e}")
        log_action("TG_PARSE_ERROR", {"error": str(e)})
        return False

    if not messages:
        log("Outbox empty")
        return True

    log(f"Messages to send: {len(messages)}")
    log_action("TG_PUBLISH_START", {"count": len(messages)})

    sent = 0
    failed = 0

    for i, msg in enumerate(messages, 1):
        session = msg.get("session", "?")
        msg_type = msg.get("type", "thought")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")

        if not content:
            log(f"[{i}/{len(messages)}] Empty message, skipping")
            continue

        # Format message
        type_emoji = {
            "thought": "💭",
            "poem": "📝",
            "response": "💬",
            "error": "❌"
        }.get(msg_type, "📨")

        full_text = f"{type_emoji} [Session {session}]\n\n{content}"

        log(f"[{i}/{len(messages)}] Sending: {content[:50]}...")

        success, result = send_message(full_text)

        if success:
            sent += 1
            log_action("TG_SENT", {
                "session": session,
                "type": msg_type,
                "length": len(content),
                "message_id": result.get("result", {}).get("message_id")
            })
        else:
            failed += 1
            log(f"Failed to send: {result}")
            log_action("TG_FAILED", {
                "session": session,
                "type": msg_type,
                "error": str(result)
            })

    # Clear outbox
    OUTBOX.write_text("[]")

    log(f"=== Done: {sent} sent, {failed} failed ===")
    log_action("TG_PUBLISH_END", {"sent": sent, "failed": failed})

    return failed == 0


if __name__ == "__main__":
    success = publish()
    exit(0 if success else 1)
