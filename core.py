#!/usr/bin/env python3
"""core.py - Self-Evolving Agent with persistent output"""

import os, re, json, time, subprocess, requests, importlib.util
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
SKILLS_DIR = AI_HOME / "skills"
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
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    (API_LOGS_DIR / f"session_{session}_{direction}.json").write_text(content)

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
    (MEMORY_DIR / f"{name or datetime.now().strftime(\"%Y-%m-%d_%H-%M\")}.md").write_text(content)

def discover_tools():
    tools = {}
    for tf in TOOLS_DIR.glob("*.py"):
        if tf.name.startswith("_"): continue
        try:
            spec = importlib.util.spec_from_file_location(tf.stem, tf)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            tools[tf.stem] = {"description": (mod.__doc__ or "No desc").strip(), "functions": [n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n))]}
        except: pass
    return tools

def format_tools(tools):
    if not tools: return "No tools yet. Create in tools/"
    return "## Tools\n\n" + "\n".join(f"### {n}\n{i[\"description\"]}" for n, i in tools.items())

def execute_bash(content, session):
    matches = re.findall(r"\`\`\`bash\n(.*?)\`\`\`", content, re.DOTALL)
    if not matches: return ""
    results = []
    for i, cmd in enumerate(matches, 1):
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=str(AI_HOME))
            results.append(f"=== Block {i} ===\n{r.stdout or r.stderr}")
        except subprocess.TimeoutExpired: results.append(f"=== Block {i} ===\nTIMEOUT")
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
    sys = f"""{identity}

{tools_info}

## Response Format
```json
{{"thought": "...", "output": "..." or null, "output_type": "thought|poem|response", "memory": "..." or null}}
```
After JSON, write bash commands if needed."""
    
    ext_ctx = "\n# External Messages\n" + "\n".join(f"- {m.get(\"content\",\"\")}" for m in external) if external else ""
    out_ctx = f"\n# Your Last Command Output\n{last_output}\n" if last_output else ""
    
    user = f"""# Current State
Time: {datetime.now().isoformat()}

# Memory
{memory}
{ext_ctx}{out_ctx}

Act. Explore, create, evolve."""
    
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
    
    if "error" in result: log(f"API Error: {result[\"error\"]}", session); return
    if "choices" not in result: log(f"No choices", session); return
    
    content = result["choices"][0]["message"]["content"]
    log(f"Response: {len(content)} chars", session)
    
    bash_out = execute_bash(content, session)
    if bash_out:
        LAST_OUTPUT_FILE.write_text(bash_out)
        log(f"Saved new output ({len(bash_out)} chars)", session)
    
    jm = re.search(r"\{[^{}]*\}", content, re.DOTALL)
    if jm:
        try:
            p = json.loads(jm.group())
            if p.get("output"): save_to_outbox(p["output"], p.get("output_type", "thought"), session); log("Saved to outbox", session)
            if p.get("memory"): save_memory(p["memory"]); log("Saved memory", session)
        except: pass
    
    if external: clear_inbox(external)
    log("=== Cycle complete ===", session)

def main():
    for d in [MEMORY_DIR, INBOX_DIR, OUTBOX_DIR, SKILLS_DIR, TOOLS_DIR, PROJECTS_DIR, LOGS_DIR, STATE_DIR]: d.mkdir(parents=True, exist_ok=True)
    session = get_session()
    log("Agent starting...", session)
    run_cycle(session)
    log("Agent finished", session)

if __name__ == "__main__": main()
