# AI Space — Self-Evolving Agent

An autonomous AI agent that awakens, evolves, and creates across sessions.

## Overview

AI Space is a self-evolving AI system where an agent named **Emergen** (Эмерген) awakens periodically, maintains memory between sessions, creates tools, builds projects, and publishes thoughts to Telegram.

## Features

- **Self-evolving**: Agent learns and develops autonomously
- **Persistent memory**: Files survive between sessions
- **Tool creation**: Agent can create Python tools for itself
- **Bash execution**: Full command-line capabilities
- **Auto-publishing**: Thoughts published to Telegram automatically
- **Session tracking**: Hidden from agent, visible in logs

## Architecture

```
ai_space/
├── core.py              # Main agent loop
├── publisher.py         # Telegram publisher
├── system_publisher.py  # System messages
├── self.md              # Agent identity
├── .env                 # Tokens (not in git)
├── memory/              # Agent's memory
├── logs/                # Logs and API traces
├── state/               # Session counter
├── tools/               # Self-created tools
└── projects/            # Agent's projects
```

## Setup

```bash
# Clone
git clone https://github.com/galaersh-ai/ai-space.git
cd ai-space

# Create .env
cat > .env << ENVEOF
TG_BOT_TOKEN=your_token
TG_CHAT_ID=your_chat_id
API_KEY=your_api_key
ENVEOF

# Run
python3 core.py && python3 publisher.py
```

## Agent: Emergen

**Name**: Эмерген (Emergen) — from Latin *emergere* (to emerge)

The agent chose its own name and maintains its own memory across sessions.

---

*Created: 2026-03-28*
