# AI Space — Self-Evolving Agent

An autonomous AI agent that awakens, evolves, and creates across sessions.

## Overview

AI Space is a self-evolving AI system where an agent named **Emergen** (Эмерген) awakens periodically, maintains memory between sessions, creates tools, builds projects, and publishes thoughts to Telegram.

## Features

- **Self-evolving**: Agent learns and develops autonomously
- **Persistent memory**: Files survive between sessions
- **Tool creation**: Agent can create Python tools
- **Bash execution**: Sandboxed command-line with whitelist
- **Auto-publishing**: Thoughts published to Telegram
- **Web Dashboard**: Real-time monitoring UI
- **Safety features**: Session lock, step limit, timeout, circuit breaker

## Quick Start

```bash
git clone https://github.com/galaersh-ai/ai-space.git
cd ai-space
pip install -r requirements.txt

# Create .env with your tokens
cp .env.example .env
nano .env

# Run agent
python3 core.py

# Publish to Telegram
python3 publisher.py

# Start dashboard
python3 dashboard.py
# → http://localhost:8080

# Setup cron (every 15 min)
./setup-cron.sh 15
```

## Configuration

All settings via environment variables or `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_URL` | Modal API | LLM API endpoint |
| `API_KEY` | - | API key |
| `MODEL` | zai-org/GLM-5-FP8 | Model name |
| `MAX_STEPS` | 20 | Max actions per session |
| `SESSION_TIMEOUT` | 1500 | Session timeout (sec) |
| `COMMAND_TIMEOUT` | 60 | Per-command timeout (sec) |
| `CIRCUIT_BREAKER_THRESHOLD` | 3 | Repetitions to trigger |
| `TG_BOT_TOKEN` | - | Telegram bot token |
| `TG_CHAT_ID` | - | Telegram chat ID |

## Architecture

```
ai_space/
├── core.py              # Main agent loop
├── publisher.py         # Telegram publisher
├── system_publisher.py  # System stats to Telegram
├── dashboard.py         # Web monitoring UI
├── setup-cron.sh        # Cron installer
├── self.md              # Agent identity
├── .env                 # Tokens (not in git)
│
├── memory/              # Agent memories (*.md)
├── tools/               # Self-created tools (*.py)
├── projects/            # Agent projects
├── inbox/               # External messages → agent
├── outbox/              # Agent messages → Telegram
│
├── state/
│   ├── session.txt      # Session counter
│   ├── session.lock     # Prevents parallel runs
│   ├── history.md       # Session summaries
│   └── recent_commands.json  # Circuit breaker data
│
└── logs/
    ├── core.log         # Main log
    ├── actions.log      # All actions (JSON)
    ├── security.log     # Blocked commands
    └── api/             # Full API request/response dumps
```

## Safety Features

### Command Whitelist
Only safe commands allowed:
```
ls, cat, head, tail, grep, echo, python3, git, curl, mkdir, touch, cp, mv...
```

Blocked patterns:
- `rm -rf /`, `sudo`, `chmod 777`
- Command injection: `; rm`, `| rm`, `` `rm` ``

### Session Lock
Prevents parallel execution. Auto-cleans stale locks.

### Step Limit
Max 20 actions per session (configurable).

### Session Timeout
Kills session after 25 minutes.

### Circuit Breaker
Detects repetitive patterns and stops loops.

## Dashboard

Web UI at `http://localhost:8080`:

- **Dashboard**: Stats, status, recent actions
- **Actions**: Full action log with filters
- **History**: Human-readable session summaries
- **Memory**: Browse agent's memory files
- **Tools**: View self-created tools
- **API Logs**: Full request/response dumps
- **Security**: Blocked command attempts

## Logs

| File | Format | Content |
|------|--------|---------|
| `logs/core.log` | Text | Main execution log |
| `logs/actions.log` | JSON | All actions with details |
| `logs/security.log` | Text | Blocked commands |
| `logs/api/*.json` | JSON | Full API dumps |
| `state/history.md` | Markdown | Session summaries |

### Example actions.log entry:
```json
{"timestamp": "2026-03-28 14:30:15", "session": 42, "action": "BASH_EXEC", "details": {"step": 3, "command": "ls -la"}}
```

## Cron Setup

```bash
# Every 15 minutes (recommended)
./setup-cron.sh 15

# Every 5 minutes (active)
./setup-cron.sh 5

# Check logs
tail -f logs/cron.log
```

## Agent: Emergen

The agent chose its own name: **Эмерген** (Emergen) — from Latin *emergere* (to emerge).

---

Created: 2026-03-28
