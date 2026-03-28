#!/usr/bin/env python3
"""core.py - Self-Evolving Agent with robust JSON parsing"""

import os, re, json, subprocess, requests, importlib.util
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

API_URL = "https://api.us-west-2.modal.direct/v1/chat/completions"
API_KEY = os.environ.get("API_KEY", "")
MODEL = "zai-org/GLM-5-FP8"

SELF_PATH = AI_HOME / "self.md"
MEMORY_DIR = AI_HOME / "memory"
INBOX_DIR = AI_HOME / "inbox"
OUTBOX_DIR = AI_HOME / "outbox"
TOOLS_DIR = AI_HOME / "tools"
PROJECTS_DIR = AI_HOME / "projects"
LOGS_DIR = AI_HOME / "logs"
STATE_DIR = AI_HOME / "state"
SESSION_FILE = STATE_DIR / "session.txt"
LAST_OUTPUT_FILE = LOGS_DIR / "last_output.txt"
API_LOGS_DIR = LOGS_DIR / "api"

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
    with open(LOGS_DIR / "core.log", "a") as f: f.write(line + "\n")

def log_api(session, direction, content):
    API_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (API_LOGS_DIR / f"session_{session}_{direction}.json").write_text(content)

def log_security(session, cmd, reason):
    """Log blocked command attempts to security.log"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [Session {session}] BLOCKED: {reason}\nCommand: {cmd[:200]}...\n{'='*50}\n"
    print(f"🚨 SECURITY: {reason}")
    with open(LOGS_DIR / "security.log", "a") as f:
        f.write(entry)

def load_self():
    return SELF_PATH.read_text() if SELF_PATH.exists() else "# Identity\n\nYou are a self-evolving AI agent.\n"

def load_memory():
    mem = [f"### {f.name}\n{f.read_text()}" for f in sorted(MEMORY_DIR.glob("*.md"), reverse=True)[:5]]
    return "\n\n".join(mem) if mem else "Memory empty. First run."

def check_inbox():
    msgs = []
    for f in INBOX_DIR.glob("*.json"):
        try: msgs.append({"source_file": str(f), **json.loads(f.read_text())})
        except: pass
    return msgs

def clear_inbox(msgs):
    for m in msgs: Path(m["source_file"]).unlink(missing_ok=True)

def save_to_outbox(content, msg_type="thought", session=None):
    out = OUTBOX_DIR / "messages.json"
    msgs = json.loads(out.read_text()) if out.exists() else []
    msgs.append({"timestamp": datetime.now().isoformat(), "session": session, "type": msg_type, "content": content})
    out.write_text(json.dumps(msgs, ensure_ascii=False, indent=2))

def save_memory(content, name=None):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    fname = name or ts
    (MEMORY_DIR / f"{fname}.md").write_text(content)

def discover_tools():
    tools = {}
    for tf in TOOLS_DIR.glob("*.py"):
        if tf.name.startswith("_"): continue
        try:
            spec = importlib.util.spec_from_file_location(tf.stem, tf)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            tools[tf.stem] = {"description": (mod.__doc__ or "No desc").strip()}
        except: pass
    return tools

def format_tools(tools):
    if not tools: return "No tools yet."
    return "## Tools\n" + ", ".join(tools.keys())

# Whitelist of allowed commands (first word of each line)
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

# Dangerous patterns (blocked even if command is allowed)
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
    # Check dangerous patterns first
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd_text, re.IGNORECASE):
            return False, f"Blocked: dangerous pattern detected"

    # Check each line's first command
    for line in cmd_text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Get first word (command)
        first_word = re.split(r'[;\s|&]', line)[0].strip()
        if first_word and first_word not in ALLOWED_COMMANDS:
            return False, f"Blocked: '{first_word}' not in whitelist"

    return True, "OK"

def execute_bash(content, session):
    matches = re.findall(r"```bash\n(.*?)```", content, re.DOTALL)
    if not matches: return ""
    results = []
    for i, cmd in enumerate(matches, 1):
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
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=str(AI_HOME))
            results.append(f"=== Block {i} ===\n{r.stdout or r.stderr}")
        except Exception as e: results.append(f"=== Block {i} ===\nError: {e}")
    return "\n\n".join(results)

def call_api(system, user, session):
    inp = {"model": MODEL, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    log_api(session, "input", json.dumps(inp, ensure_ascii=False, indent=2))
    try:
        resp = requests.post(API_URL, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, json=inp, timeout=120)
        out = resp.json()
        log_api(session, "output", json.dumps(out, ensure_ascii=False, indent=2))
        return out
    except Exception as e: return {"error": str(e)}

def think(identity, memory, external, tools, last_output, session):
    tools_info = format_tools(tools)
    sys = f"{identity}\n\n{tools_info}"
    ext_ctx = "\n# External Messages\n" + "\n".join(f"- {m.get('content', '')}" for m in external) if external else ""
    out_ctx = f"\n# Your Last Command Output\n{last_output}\n" if last_output else ""
    user = f"# Current State\nTime: {datetime.now().isoformat()}\n\n# Memory\n{memory}\n{ext_ctx}{out_ctx}\n\nAct. Explore, create, evolve. REMEMBER: Output field in JSON is REQUIRED."
    return call_api(sys, user, session)

def run_cycle(session):
    log("=== Cycle start ===", session)
    
    identity = load_self()
    memory = load_memory()
    external = check_inbox()
    tools = discover_tools()
    last_output = LAST_OUTPUT_FILE.read_text() if LAST_OUTPUT_FILE.exists() else ""
    
    log(f"Tools: {len(tools)}, External: {len(external)}, LastOutput: {len(last_output)} chars", session)
    
    result = think(identity, memory, external, tools, last_output, session)
    
    if "error" in result: log(f"API Error: {result['error']}", session); return
    if "choices" not in result: log(f"No choices", session); return
    
    content = result["choices"][0]["message"]["content"]
    log(f"Response: {len(content)} chars", session)
    
    # Execute bash
    bash_out = execute_bash(content, session)
    if bash_out:
        LAST_OUTPUT_FILE.write_text(bash_out)
        log(f"Saved new output ({len(bash_out)} chars)", session)
    
    # Try to find JSON
    published = False
    jm = re.search(r"\{[^{}]*\}", content, re.DOTALL)
    if jm:
        try:
            p = json.loads(jm.group())
            if p.get("output"):
                save_to_outbox(p["output"], p.get("output_type", "thought"), session)
                log(f"Published: {p['output'][:50]}...", session)
                published = True
            elif p.get("thought"):
                save_to_outbox(p["thought"], "thought", session)
                log(f"Published thought: {p['thought'][:50]}...", session)
                published = True
            if p.get("memory"): 
                save_memory(p["memory"])
                log("Saved memory", session)
        except: pass
    
    # If no JSON found, publish whole response
    if not published:
        # Clean up bash blocks for publication
        clean_content = re.sub(r"```bash\n.*?```", "", content, flags=re.DOTALL).strip()
        if clean_content:
            save_to_outbox(clean_content[:500], "thought", session)
            log(f"Published raw content (no JSON found)", session)
    
    if external: clear_inbox(external)
    log("=== Cycle complete ===", session)

def main():
    for d in [MEMORY_DIR, INBOX_DIR, OUTBOX_DIR, TOOLS_DIR, PROJECTS_DIR, LOGS_DIR, STATE_DIR]: d.mkdir(parents=True, exist_ok=True)
    session = get_session()
    log("Agent starting...", session)
    run_cycle(session)
    log("Agent finished", session)

if __name__ == "__main__": main()
