"""Shared configuration utilities for ai-space"""

import os
from pathlib import Path

# Use home directory instead of hardcoded /root
AI_HOME = Path(os.environ.get("AI_SPACE_HOME", Path.home() / "ai_space"))


def load_env(env_path: Path = None) -> None:
    """Load environment variables from .env file"""
    env_file = env_path or (AI_HOME / ".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def get_dirs() -> dict:
    """Return all standard directories"""
    return {
        "home": AI_HOME,
        "memory": AI_HOME / "memory",
        "inbox": AI_HOME / "inbox",
        "outbox": AI_HOME / "outbox",
        "tools": AI_HOME / "tools",
        "projects": AI_HOME / "projects",
        "logs": AI_HOME / "logs",
        "state": AI_HOME / "state",
    }


def ensure_dirs() -> None:
    """Create all required directories"""
    for path in get_dirs().values():
        path.mkdir(parents=True, exist_ok=True)
