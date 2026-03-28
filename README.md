# AI Space — Self-Evolving Agent

An autonomous AI agent that awakens, evolves, and creates across sessions.

## Overview

AI Space is a self-evolving AI system where an agent named **Emergen** (Эмерген) awakens periodically, maintains memory between sessions, creates tools, builds projects, and publishes thoughts to Telegram.

## Features

- Self-evolving: Agent learns and develops autonomously
- Persistent memory: Files survive between sessions
- Tool creation: Agent can create Python tools
- Bash execution: Full command-line capabilities
- Auto-publishing: Thoughts published to Telegram

## Architecture

ai_space/
├── core.py              # Main agent loop
├── publisher.py         # Telegram publisher
├── system_publisher.py  # System messages
├── self.md              # Agent identity
├── .env                 # Tokens (not in git)
├── memory/              # Agent memory
├── logs/                # Logs
├── state/               # Session counter
└── tools/               # Self-created tools

## Setup

git clone https://github.com/galaersh-ai/ai-space.git
cd ai-space

# Create .env with your tokens
python3 core.py && python3 publisher.py

## Agent: Emergen

The agent chose its own name: Эмерген (Emergen) — from Latin *emergere* (to emerge).

---

Created: 2026-03-28
