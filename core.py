#!/usr/bin/env python3
"""core.py - Self-Evolving Agent with robust JSON parsing"""

import os
import re
import json
import subprocess
import requests
import importlib.util
import signal
import sys
import atexit
from datetime import datetime
from pathlib import Path

AI_HOME = Path("/root/ai_space")

# Load .env FIRST
env_file = AI_HOME / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

# === CONFIGURATION ===
API_URL = os.environ.get("API_URL", "https://api.us-west-2.modal.direct/v1/chat/completions")
API_KEY = os.environ.get("API_KEY", "")
MODEL = os.environ.get("MODEL", "zai-org/GLM-5-FP8")

# Limits
MAX_STEPS = int(os.environ.get("MAX_STEPS", "20"))
SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "1800"))  # 30 min
COMMAND_TIMEOUT = int(os.environ.get("COMMAND_TIMEOUT", "60"))

# === PATHS ===
SELF_PATH = AI_HOME / "self.md"
MEMORY_DIR = AI_HOME / "memory"
INBOX_DIR = AI_HOME / "inbox"
OUTBOX_DIR = AI_HOME / "outbox"
TOOLS_DIR = AI_HOME / "tools"
PROJECTS_DIR = AI_HOME / "projects"
LOGS_DIR = AI_HOME / "logs"
STATE_DIR = AI_HOME / "state"
SESSION_FILE = STATE_DIR / "session.txt"
LOCK_FILE = STATE_DIR / "session.lock"
LAST_OUTPUT_FILE = LOGS_DIR / "last_output.txt"
API_LOGS_DIR = LOGS_DIR / "api"
HISTORY_FILE = STATE_DIR / "history.md"

# === SESSION LOCK ===
def acquire_lock(session):
    """Acquire session lock. Returns False if another session is running."""
    if LOCK_FILE.exists():
        try:
            lock_data = json.loads(LOCK_FILE.read_text())
            pid = lock_data.get("pid")
            # Check if process is still running
            if pid and os.path.exists(f"/proc/{pid}"):
                log(f"Another session is running (PID {pid})", session)
                return False
            else:
                log(f"Stale lock found, removing", session)
        except:
            pass

    # Create lock
    lock_data = {
        "session": session,
        "pid": os.getpid(),
        "started": datetime.now().isoformat()
    }
    LOCK_FILE.write_text(json.dumps(lock_data))
    log(f"Lock acquired (PID {os.getpid()})", session)
    return True

def release_lock():
    """Release session lock."""
    if LOCK_FILE.exists():
        LOCK_FILE.unlink(missing_ok=True)

# Register cleanup on exit
atexit.register(release_lock)

# === TIMEOUT HANDLER ===
def timeout_handler(signum, frame):
    log("⏰ SESSION TIMEOUT - forcing exit", None)
    release_lock()
    sys.exit(1)

# === LOGGING ===
def get_session():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    num = int(SESSION_FILE.read_text().strip()) if SESSION_FILE.exists() else 0
    num += 1
    SESSION_FILE.write_text(str(num))
    return num

def log(msg, session=None):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = f"[Session {session}] " if session else ""
    line = f"[{ts}] {prefix}{msg}"
    print(line)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOGS_DIR / "core.log", "a") as f:
        f.write(line + "\n")

def log_action(session, action_type, details):
    """Log all actions to actions.log with full details"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": ts,
        "session": session,
        "action": action_type,
        "details": details
    }
    with open(LOGS_DIR / "actions.log", "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    log(f"ACTION: {action_type}", session)

def log_api(session, direction, content):
    """Log API calls with full request/response"""
    API_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H-%M-%S")
    filename = f"session_{session}_{ts}_{direction}.json"
    (API_LOGS_DIR / filename).write_text(content)

    # Also log summary to actions.log
    try:
        data = json.loads(content)
        if direction == "input":
            log_action(session, "API_REQUEST", {
                "model": data.get("model"),
                "messages_count": len(data.get("messages", [])),
                "prompt_preview": data.get("messages", [{}])[-1].get("content", "")[:100]
            })
        else:
            usage = data.get("usage", {})
            log_action(session, "API_RESPONSE", {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "response_preview": data.get("choices", [{}])[0].get("message", {}).get("content", "")[:100]
            })
    except:
        pass

def log_security(session, cmd, reason):
    """Log blocked command attempts to security.log"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [Session {session}] BLOCKED: {reason}\nCommand: {cmd[:200]}...\n{'='*50}\n"
    print(f"🚨 SECURITY: {reason}")
    with open(LOGS_DIR / "security.log", "a") as f:
        f.write(entry)
    log_action(session, "SECURITY_BLOCK", {"reason": reason, "command": cmd[:200]})

def append_history(session, summary):
    """Append session summary to history.md"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## Session {session} ({ts})\n{summary}\n"
    with open(HISTORY_FILE, "a") as f:
        f.write(entry)

# === CORE FUNCTIONS ===
def load_self():
    return SELF_PATH.read_text() if SELF_PATH.exists() else "# Identity\n\nYou are a self-evolving AI agent.\n"

def load_memory():
    mem = [f"### {f.name}\n{f.read_text()}" for f in sorted(MEMORY_DIR.glob("*.md"), reverse=True)[:5]]
    return "\n\n".join(mem) if mem else "Memory empty. First run."

def check_inbox():
    msgs = []
    for f in INBOX_DIR.glob("*.json"):
        try:
            msgs.append({"source_file": str(f), **json.loads(f.read_text())})
        except:
            pass
    return msgs

def clear_inbox(msgs):
    for m in msgs:
        Path(m["source_file"]).unlink(missing_ok=True)

def save_to_outbox(content, msg_type="thought", session=None):
    out = OUTBOX_DIR / "messages.json"
    msgs = json.loads(out.read_text()) if out.exists() else []
    msgs.append({"timestamp": datetime.now().isoformat(), "session": session, "type": msg_type, "content": content})
    out.write_text(json.dumps(msgs, ensure_ascii=False, indent=2))
    log_action(session, "OUTBOX_WRITE", {"type": msg_type, "length": len(content)})

def save_memory(content, name=None, session=None):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    fname = name or ts
    (MEMORY_DIR / f"{fname}.md").write_text(content)
    log_action(session, "MEMORY_SAVE", {"filename": fname, "length": len(content)})

def discover_tools():
    tools = {}
    for tf in TOOLS_DIR.glob("*.py"):
        if tf.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(tf.stem, tf)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            tools[tf.stem] = {"description": (mod.__doc__ or "No desc").strip()}
        except:
            pass
    return tools

def format_tools(tools):
    if not tools:
        return "No tools yet."
    return "## Tools\n" + ", ".join(tools.keys())

# === COMMAND WHITELIST ===
ALLOWED_COMMANDS = {
    # File operations (safe within AI_HOME)
    "ls", "cat", "head", "tail", "wc", "find", "tree",
    "mkdir", "touch", "cp", "mv",
    # Text processing
    "echo", "printf", "grep", "sed", "awk", "sort", "uniq", "cut",
    # Python
    "python", "python3", "pip", "pip3",
    # Git (read operations)
    "git",
    # Network (limited)
    "curl", "wget",
    # System info
    "date", "pwd", "whoami", "env", "which",
}

DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\s+/",      # rm -rf /
    r"\brm\s+-rf\s+~",      # rm -rf ~
    r">\s*/etc/",           # write to /etc
    r">\s*/usr/",           # write to /usr
    r"\bsudo\b",            # sudo
    r"\bchmod\s+777",       # chmod 777
    r"\bdd\s+if=",          # dd
    r"\bmkfs\b",            # mkfs
    r";\s*rm\s",            # ; rm (command injection)
    r"\|\s*rm\s",           # | rm (pipe to rm)
    r"`rm\s",               # `rm (backtick injection)
    r"\$\(rm\s",            # $(rm (subshell injection)
]

def is_command_safe(cmd_text):
    """Check if command is in whitelist and doesn't contain dangerous patterns"""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd_text, re.IGNORECASE):
            return False, "Blocked: dangerous pattern detected"

    for line in cmd_text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        first_word = re.split(r'[;\s|&]', line)[0].strip()
        if first_word and first_word not in ALLOWED_COMMANDS:
            return False, f"Blocked: '{first_word}' not in whitelist"

    return True, "OK"

def execute_bash(content, session, step_counter):
    """Execute bash commands with logging"""
    matches = re.findall(r"```bash\n(.*?)```", content, re.DOTALL)
    if not matches:
        return "", step_counter

    results = []
    for i, cmd in enumerate(matches, 1):
        step_counter += 1

        # Check step limit
        if step_counter > MAX_STEPS:
            msg = f"Step limit reached ({MAX_STEPS}). Stopping execution."
            log(msg, session)
            log_action(session, "STEP_LIMIT", {"max_steps": MAX_STEPS})
            results.append(f"=== Block {i} ===\n⚠️ {msg}")
            break

        is_safe, reason = is_command_safe(cmd)
        if not is_safe:
            blocked_msg = f"""=== Block {i} ===
⚠️ COMMAND BLOCKED: {reason}

Your command was blocked for security reasons.
Allowed commands: {', '.join(sorted(ALLOWED_COMMANDS))}

Try using an allowed command instead."""
            results.append(blocked_msg)
            log(f"Command blocked: {reason}", session)
            log_security(session, cmd, reason)
            continue

        # Log command execution
        log_action(session, "BASH_EXEC", {"step": step_counter, "command": cmd[:200]})

        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=COMMAND_TIMEOUT, cwd=str(AI_HOME)
            )
            output = r.stdout or r.stderr
            results.append(f"=== Block {i} ===\n{output}")
            log_action(session, "BASH_RESULT", {
                "step": step_counter,
                "exit_code": r.returncode,
                "output_length": len(output)
            })
        except subprocess.TimeoutExpired:
            msg = f"Command timeout ({COMMAND_TIMEOUT}s)"
            results.append(f"=== Block {i} ===\nError: {msg}")
            log_action(session, "BASH_TIMEOUT", {"step": step_counter, "timeout": COMMAND_TIMEOUT})
        except Exception as e:
            results.append(f"=== Block {i} ===\nError: {e}")
            log_action(session, "BASH_ERROR", {"step": step_counter, "error": str(e)})

    return "\n\n".join(results), step_counter

def call_api(system, user, session):
    """Call LLM API with full logging"""
    inp = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    }
    log_api(session, "input", json.dumps(inp, ensure_ascii=False, indent=2))

    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json=inp,
            timeout=120
        )
        out = resp.json()
        log_api(session, "output", json.dumps(out, ensure_ascii=False, indent=2))
        return out
    except Exception as e:
        log_action(session, "API_ERROR", {"error": str(e)})
        return {"error": str(e)}

def think(identity, memory, external, tools, last_output, session):
    tools_info = format_tools(tools)
    sys_prompt = f"{identity}\n\n{tools_info}"
    ext_ctx = "\n# External Messages\n" + "\n".join(f"- {m.get('content', '')}" for m in external) if external else ""
    out_ctx = f"\n# Your Last Command Output\n{last_output}\n" if last_output else ""
    user = f"# Current State\nTime: {datetime.now().isoformat()}\n\n# Memory\n{memory}\n{ext_ctx}{out_ctx}\n\nAct. Explore, create, evolve. REMEMBER: Output field in JSON is REQUIRED."
    return call_api(sys_prompt, user, session)

# === MAIN CYCLE ===
def run_cycle(session):
    log("=== Cycle start ===", session)
    log_action(session, "CYCLE_START", {
        "max_steps": MAX_STEPS,
        "session_timeout": SESSION_TIMEOUT,
        "model": MODEL
    })

    step_counter = 0

    identity = load_self()
    memory = load_memory()
    external = check_inbox()
    tools = discover_tools()
    last_output = LAST_OUTPUT_FILE.read_text() if LAST_OUTPUT_FILE.exists() else ""

    log(f"Tools: {len(tools)}, External: {len(external)}, LastOutput: {len(last_output)} chars", session)

    result = think(identity, memory, external, tools, last_output, session)
    step_counter += 1

    if "error" in result:
        log(f"API Error: {result['error']}", session)
        append_history(session, f"Error: {result['error']}")
        return
    if "choices" not in result:
        log("No choices in response", session)
        append_history(session, "Error: No choices in API response")
        return

    content = result["choices"][0]["message"]["content"]
    log(f"Response: {len(content)} chars", session)

    # Execute bash
    bash_out, step_counter = execute_bash(content, session, step_counter)
    if bash_out:
        LAST_OUTPUT_FILE.write_text(bash_out)
        log(f"Saved new output ({len(bash_out)} chars)", session)

    # Try to find JSON
    published = False
    summary_parts = []

    jm = re.search(r"\{[^{}]*\}", content, re.DOTALL)
    if jm:
        try:
            p = json.loads(jm.group())
            if p.get("output"):
                save_to_outbox(p["output"], p.get("output_type", "thought"), session)
                log(f"Published: {p['output'][:50]}...", session)
                published = True
                summary_parts.append(f"Published: {p['output'][:100]}")
            elif p.get("thought"):
                save_to_outbox(p["thought"], "thought", session)
                log(f"Published thought: {p['thought'][:50]}...", session)
                published = True
                summary_parts.append(f"Thought: {p['thought'][:100]}")
            if p.get("memory"):
                save_memory(p["memory"], session=session)
                log("Saved memory", session)
                summary_parts.append("Saved memory")
        except:
            pass

    # If no JSON found, publish whole response
    if not published:
        clean_content = re.sub(r"```bash\n.*?```", "", content, flags=re.DOTALL).strip()
        if clean_content:
            save_to_outbox(clean_content[:500], "thought", session)
            log("Published raw content (no JSON found)", session)
            summary_parts.append(f"Raw output: {clean_content[:100]}")

    if external:
        clear_inbox(external)
        summary_parts.append(f"Processed {len(external)} external messages")

    # Log final stats
    log_action(session, "CYCLE_END", {"total_steps": step_counter})
    append_history(session, "\n".join(summary_parts) if summary_parts else "No significant actions")

    log(f"=== Cycle complete (steps: {step_counter}/{MAX_STEPS}) ===", session)

def main():
    # Create directories
    for d in [MEMORY_DIR, INBOX_DIR, OUTBOX_DIR, TOOLS_DIR, PROJECTS_DIR, LOGS_DIR, STATE_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    session = get_session()
    log("Agent starting...", session)
    log(f"Config: MAX_STEPS={MAX_STEPS}, TIMEOUT={SESSION_TIMEOUT}s, MODEL={MODEL}", session)

    # Acquire lock
    if not acquire_lock(session):
        log("Could not acquire lock, exiting", session)
        sys.exit(1)

    # Set session timeout (Unix only)
    try:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(SESSION_TIMEOUT)
        log(f"Session timeout set: {SESSION_TIMEOUT}s", session)
    except (AttributeError, ValueError):
        log("Warning: Session timeout not available on this platform", session)

    try:
        run_cycle(session)
    finally:
        release_lock()
        try:
            signal.alarm(0)  # Cancel timeout
        except:
            pass

    log("Agent finished", session)

if __name__ == "__main__":
    main()
