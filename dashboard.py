#!/usr/bin/env python3
"""
dashboard.py - Web dashboard for AI Space monitoring

Run: python3 dashboard.py
Open: http://localhost:8080
"""

import os
import json
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote, unquote
import html

AI_HOME = Path("/root/ai_space")
LOGS_DIR = AI_HOME / "logs"
STATE_DIR = AI_HOME / "state"
MEMORY_DIR = AI_HOME / "memory"
TOOLS_DIR = AI_HOME / "tools"
PROJECTS_DIR = AI_HOME / "projects"
OUTBOX_DIR = AI_HOME / "outbox"
INBOX_DIR = AI_HOME / "inbox"
SELF_PATH = AI_HOME / "self.md"

PORT = int(os.environ.get("DASHBOARD_PORT", "8080"))


def get_session_count():
    f = STATE_DIR / "session.txt"
    return int(f.read_text().strip()) if f.exists() else 0


def get_lock_status():
    f = STATE_DIR / "session.lock"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except:
        return {"error": "invalid lock file"}


def get_recent_actions(limit=50):
    f = LOGS_DIR / "actions.log"
    if not f.exists():
        return []
    lines = f.read_text().strip().split("\n")[-limit:]
    actions = []
    for line in reversed(lines):
        try:
            actions.append(json.loads(line))
        except:
            pass
    return actions


def get_history():
    f = STATE_DIR / "history.md"
    return f.read_text() if f.exists() else "No history yet."


def get_file_list(directory, pattern="*"):
    if not directory.exists():
        return []
    files = []
    for f in sorted(directory.glob(pattern), key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True):
        if f.is_file():
            files.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            })
    return files[:20]


def read_file_safe(filepath, max_size=50000):
    try:
        # Decode URL-encoded path
        filepath = unquote(filepath)
        p = Path(filepath)
        # Security: only allow files within AI_HOME
        if not str(p.resolve()).startswith(str(AI_HOME.resolve())):
            return "Access denied: file outside AI_HOME"
        if not p.exists():
            return f"File not found: {filepath}"
        if p.stat().st_size > max_size:
            return p.read_text(errors='replace')[:max_size] + f"\n\n... (truncated, {p.stat().st_size} bytes total)"
        return p.read_text(errors='replace')
    except Exception as e:
        return f"Error reading file: {e}"


def format_api_json_pretty(filepath):
    """Format API JSON file in a human-readable way"""
    try:
        content = read_file_safe(filepath)
        data = json.loads(content)

        sections = []

        # For input (request)
        if "messages" in data:
            sections.append(('<span class="section-title">Model</span>', html.escape(data.get("model", "?"))))

            for msg in data.get("messages", []):
                role = msg.get("role", "?")
                content = msg.get("content", "")
                role_class = "role-system" if role == "system" else "role-user"
                sections.append((f'<span class="section-title {role_class}">{role.upper()}</span>',
                               html.escape(content)))

        # For output (response)
        if "choices" in data:
            # Usage stats
            usage = data.get("usage", {})
            if usage:
                usage_text = f"Prompt: {usage.get('prompt_tokens', 0)} | Completion: {usage.get('completion_tokens', 0)} | Total: {usage.get('total_tokens', 0)}"
                sections.append(('<span class="section-title">Tokens</span>', usage_text))

            # Model response
            for choice in data.get("choices", []):
                msg = choice.get("message", {})
                content = msg.get("content", "")
                sections.append(('<span class="section-title role-assistant">ASSISTANT</span>',
                               html.escape(content)))

        # Error
        if "error" in data:
            sections.append(('<span class="section-title" style="color: #f85149;">ERROR</span>',
                           html.escape(str(data["error"]))))

        return sections
    except:
        return None


def get_api_logs():
    api_dir = LOGS_DIR / "api"
    if not api_dir.exists():
        return []
    files = []
    for f in sorted(api_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
        files.append({
            "name": f.name,
            "path": str(f),
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        })
    return files


def get_security_log():
    f = LOGS_DIR / "security.log"
    return f.read_text() if f.exists() else "No security events."


def get_core_log(lines=100):
    f = LOGS_DIR / "core.log"
    if not f.exists():
        return "No core log yet."
    all_lines = f.read_text().strip().split("\n")
    return "\n".join(all_lines[-lines:])


def get_outbox_messages():
    f = OUTBOX_DIR / "messages.json"
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text())
    except:
        return []


def get_inbox_messages():
    files = get_file_list(INBOX_DIR, "*.json")
    messages = []
    for f in files:
        try:
            data = json.loads(Path(f["path"]).read_text())
            messages.append({**f, "content": data})
        except:
            messages.append(f)
    return messages


def get_stats():
    stats = {
        "sessions": get_session_count(),
        "memory_files": len(list(MEMORY_DIR.glob("*.md"))) if MEMORY_DIR.exists() else 0,
        "tools": len(list(TOOLS_DIR.glob("*.py"))) if TOOLS_DIR.exists() else 0,
        "projects": len(list(PROJECTS_DIR.iterdir())) if PROJECTS_DIR.exists() else 0,
        "inbox": len(list(INBOX_DIR.glob("*.json"))) if INBOX_DIR.exists() else 0,
        "outbox": len(get_outbox_messages()),
    }

    # Token usage from recent API logs
    api_dir = LOGS_DIR / "api"
    total_tokens = 0
    if api_dir.exists():
        for f in api_dir.glob("*_output.json"):
            try:
                data = json.loads(f.read_text())
                total_tokens += data.get("usage", {}).get("total_tokens", 0)
            except:
                pass
    stats["total_tokens"] = total_tokens

    return stats


def get_all_files_stats():
    """Get counts of all file types for the file bar"""
    stats = []

    # Memory
    count = len(list(MEMORY_DIR.glob("*.md"))) if MEMORY_DIR.exists() else 0
    if count: stats.append(("memory", count, "#8b5cf6"))

    # Tools
    count = len(list(TOOLS_DIR.glob("*.py"))) if TOOLS_DIR.exists() else 0
    if count: stats.append(("tools", count, "#3b82f6"))

    # Projects
    count = len(list(PROJECTS_DIR.iterdir())) if PROJECTS_DIR.exists() else 0
    if count: stats.append(("projects", count, "#10b981"))

    # Inbox
    count = len(list(INBOX_DIR.glob("*.json"))) if INBOX_DIR.exists() else 0
    if count: stats.append(("inbox", count, "#f59e0b"))

    # Outbox
    count = len(get_outbox_messages())
    if count: stats.append(("outbox", count, "#ef4444"))

    return stats


def get_api_logs_filtered(session_filter=None, limit=20):
    """Get API logs with optional session filter"""
    api_dir = LOGS_DIR / "api"
    if not api_dir.exists():
        return [], 0

    all_files = list(api_dir.iterdir())
    total_count = len(all_files)

    # Filter by session if provided
    if session_filter:
        all_files = [f for f in all_files if f"session_{session_filter}_" in f.name]

    # Sort by modification time
    all_files = sorted(all_files, key=lambda x: x.stat().st_mtime, reverse=True)

    # Apply limit (0 = no limit)
    if limit > 0:
        all_files = all_files[:limit]

    files = []
    for f in all_files:
        files.append({
            "name": f.name,
            "path": str(f),
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        })
    return files, total_count


# HTML Templates
def html_page(title, content, nav_active=""):
    nav_items = [
        ("Dashboard", "/"),
        ("Actions", "/actions"),
        ("History", "/history"),
        ("Identity", "/identity"),
        ("Memory", "/memory"),
        ("Tools", "/tools"),
        ("Projects", "/projects"),
        ("Inbox", "/inbox"),
        ("Outbox", "/outbox"),
        ("API Logs", "/api-logs"),
        ("Core Log", "/core-log"),
        ("Security", "/security"),
    ]
    nav_html = "".join([
        f'<a href="{url}" class="{"active" if nav_active == name else ""}">{name}</a>'
        for name, url in nav_items
    ])

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>{title} - AI Space</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; }}
        .header {{ background: #161b22; padding: 1rem 2rem; border-bottom: 1px solid #30363d; }}
        .header h1 {{ color: #58a6ff; font-size: 1.5rem; }}
        .nav {{ background: #161b22; padding: 0.5rem 2rem; border-bottom: 1px solid #30363d; display: flex; gap: 0.5rem; flex-wrap: wrap; }}
        .nav a {{ color: #8b949e; text-decoration: none; padding: 0.4rem 0.8rem; border-radius: 6px; font-size: 0.9rem; }}
        .nav a:hover {{ background: #21262d; color: #c9d1d9; }}
        .nav a.active {{ background: #21262d; color: #58a6ff; }}
        .content {{ padding: 2rem; max-width: 1400px; margin: 0 auto; }}
        .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }}
        .card h2 {{ color: #58a6ff; font-size: 1rem; margin-bottom: 0.5rem; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 1rem; }}
        .stat {{ text-align: center; }}
        .stat .value {{ font-size: 2rem; color: #58a6ff; }}
        .stat .label {{ color: #8b949e; font-size: 0.85rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 0.5rem; text-align: left; border-bottom: 1px solid #30363d; }}
        th {{ color: #8b949e; font-weight: normal; }}
        pre {{ background: #0d1117; padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: 0.85rem; white-space: pre-wrap; word-wrap: break-word; }}
        code {{ font-family: 'Fira Code', Consolas, monospace; }}
        .badge {{ display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; }}
        .badge-green {{ background: #238636; color: white; }}
        .badge-red {{ background: #da3633; color: white; }}
        .badge-yellow {{ background: #9e6a03; color: white; }}
        .badge-blue {{ background: #1f6feb; color: white; }}
        .badge-purple {{ background: #8b5cf6; color: white; }}
        a {{ color: #58a6ff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .file-list {{ list-style: none; }}
        .file-list li {{ padding: 0.5rem 0; border-bottom: 1px solid #21262d; }}
        .file-list li:last-child {{ border-bottom: none; }}
        .lock-active {{ color: #f85149; }}
        .file-bar {{ display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin-bottom: 1rem; background: #21262d; }}
        .file-bar-segment {{ height: 100%; }}
        .file-bar-legend {{ display: flex; gap: 1rem; flex-wrap: wrap; font-size: 0.8rem; color: #8b949e; }}
        .file-bar-legend span {{ display: flex; align-items: center; gap: 0.3rem; }}
        .file-bar-legend .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
        .empty {{ color: #8b949e; font-style: italic; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>AI Space Dashboard</h1>
    </div>
    <nav class="nav">{nav_html}</nav>
    <div class="content">{content}</div>
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>"""


def make_file_link(filepath, name=None):
    """Create a safe link to view a file"""
    encoded_path = quote(str(filepath), safe='')
    display_name = name or Path(filepath).name
    return f'<a href="/file?path={encoded_path}">{html.escape(display_name)}</a>'


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        routes = {
            "/": self.send_dashboard,
            "/actions": self.send_actions,
            "/history": self.send_history,
            "/identity": self.send_identity,
            "/memory": self.send_memory,
            "/tools": self.send_tools,
            "/projects": self.send_projects,
            "/inbox": self.send_inbox,
            "/outbox": self.send_outbox,
            "/api-logs": self.send_api_logs,
            "/core-log": self.send_core_log,
            "/security": self.send_security,
        }

        if path == "/api-logs":
            session = query.get("session", [""])[0]
            show_all = query.get("all", [""])[0] == "1"
            self.send_api_logs(session_filter=session, show_all=show_all)
        elif path in routes:
            routes[path]()
        elif path == "/file":
            filepath = query.get("path", [""])[0]
            raw = query.get("raw", [""])[0] == "1"
            self.send_file_view(filepath, raw=raw)
        else:
            self.send_error(404)

    def send_html(self, content):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def send_dashboard(self):
        stats = get_stats()
        lock = get_lock_status()
        recent = get_recent_actions(10)
        file_stats = get_all_files_stats()

        # File bar
        total_files = sum(s[1] for s in file_stats) or 1
        bar_html = ""
        legend_html = ""
        for name, count, color in file_stats:
            width = (count / total_files) * 100
            bar_html += f'<div class="file-bar-segment" style="width: {width}%; background: {color};" title="{name}: {count}"></div>'
            legend_html += f'<span><span class="dot" style="background: {color};"></span>{name}: {count}</span>'

        lock_html = ""
        if lock:
            lock_html = f'<p class="lock-active">Session {lock.get("session")} running (PID {lock.get("pid")})</p>'
        else:
            lock_html = '<p style="color: #3fb950;">No active session</p>'

        actions_html = ""
        for a in recent:
            badge_class = "badge-blue"
            if "ERROR" in a.get("action", ""):
                badge_class = "badge-red"
            elif "SECURITY" in a.get("action", ""):
                badge_class = "badge-yellow"
            elif "API" in a.get("action", ""):
                badge_class = "badge-green"
            elif "TG" in a.get("action", ""):
                badge_class = "badge-purple"
            actions_html += f'''<tr>
                <td>{a.get("timestamp", "")}</td>
                <td><span class="badge {badge_class}">{a.get("action", "")}</span></td>
                <td>Session {a.get("session", "?")}</td>
            </tr>'''

        content = f"""
        <div class="card">
            <h2>Files Created</h2>
            <div class="file-bar">{bar_html}</div>
            <div class="file-bar-legend">{legend_html}</div>
        </div>

        <div class="stats">
            <div class="card stat"><div class="value">{stats['sessions']}</div><div class="label">Sessions</div></div>
            <div class="card stat"><div class="value">{stats['memory_files']}</div><div class="label">Memory</div></div>
            <div class="card stat"><div class="value">{stats['tools']}</div><div class="label">Tools</div></div>
            <div class="card stat"><div class="value">{stats['projects']}</div><div class="label">Projects</div></div>
            <div class="card stat"><div class="value">{stats['outbox']}</div><div class="label">Outbox</div></div>
            <div class="card stat"><div class="value">{stats['total_tokens']:,}</div><div class="label">Tokens</div></div>
        </div>

        <div class="card">
            <h2>Status</h2>
            {lock_html}
        </div>

        <div class="card">
            <h2>Recent Actions</h2>
            <table>
                <tr><th>Time</th><th>Action</th><th>Session</th></tr>
                {actions_html if actions_html else '<tr><td colspan="3" class="empty">No actions yet</td></tr>'}
            </table>
            <p style="margin-top: 1rem;"><a href="/actions">View all actions &rarr;</a></p>
        </div>
        """
        self.send_html(html_page("Dashboard", content, "Dashboard"))

    def send_actions(self):
        actions = get_recent_actions(100)
        rows = ""
        for a in actions:
            details = html.escape(json.dumps(a.get("details", {}), ensure_ascii=False)[:100])
            rows += f'''<tr>
                <td>{a.get("timestamp", "")}</td>
                <td>{a.get("session", "?")}</td>
                <td><span class="badge badge-blue">{a.get("action", "")}</span></td>
                <td><code>{details}</code></td>
            </tr>'''

        content = f"""
        <div class="card">
            <h2>All Actions (last 100)</h2>
            <table>
                <tr><th>Time</th><th>Session</th><th>Action</th><th>Details</th></tr>
                {rows if rows else '<tr><td colspan="4" class="empty">No actions yet</td></tr>'}
            </table>
        </div>
        """
        self.send_html(html_page("Actions", content, "Actions"))

    def send_history(self):
        history = html.escape(get_history())
        content = f"""
        <div class="card">
            <h2>Session History</h2>
            <pre><code>{history}</code></pre>
        </div>
        """
        self.send_html(html_page("History", content, "History"))

    def send_identity(self):
        identity = html.escape(read_file_safe(str(SELF_PATH)))
        content = f"""
        <div class="card">
            <h2>Agent Identity (self.md)</h2>
            <p style="color: #8b949e; margin-bottom: 1rem;">{SELF_PATH}</p>
            <pre><code>{identity}</code></pre>
        </div>
        """
        self.send_html(html_page("Identity", content, "Identity"))

    def send_memory(self):
        files = get_file_list(MEMORY_DIR, "*.md")
        rows = ""
        for f in files:
            rows += f'''<tr>
                <td>{make_file_link(f["path"], f["name"])}</td>
                <td>{f["size"]} bytes</td>
                <td>{f["modified"]}</td>
            </tr>'''

        content = f"""
        <div class="card">
            <h2>Memory Files</h2>
            <table>
                <tr><th>Name</th><th>Size</th><th>Modified</th></tr>
                {rows if rows else '<tr><td colspan="3" class="empty">No memory files yet</td></tr>'}
            </table>
        </div>
        """
        self.send_html(html_page("Memory", content, "Memory"))

    def send_tools(self):
        files = get_file_list(TOOLS_DIR, "*.py")
        rows = ""
        for f in files:
            rows += f'''<tr>
                <td>{make_file_link(f["path"], f["name"])}</td>
                <td>{f["size"]} bytes</td>
                <td>{f["modified"]}</td>
            </tr>'''

        content = f"""
        <div class="card">
            <h2>Agent Tools</h2>
            <table>
                <tr><th>Name</th><th>Size</th><th>Modified</th></tr>
                {rows if rows else '<tr><td colspan="3" class="empty">No tools yet</td></tr>'}
            </table>
        </div>
        """
        self.send_html(html_page("Tools", content, "Tools"))

    def send_projects(self):
        if not PROJECTS_DIR.exists():
            rows = ""
        else:
            rows = ""
            for p in sorted(PROJECTS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
                if p.is_dir():
                    file_count = len(list(p.rglob("*")))
                    rows += f'''<tr>
                        <td>{html.escape(p.name)}/</td>
                        <td>{file_count} files</td>
                        <td>{datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")}</td>
                    </tr>'''
                else:
                    rows += f'''<tr>
                        <td>{make_file_link(str(p), p.name)}</td>
                        <td>{p.stat().st_size} bytes</td>
                        <td>{datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")}</td>
                    </tr>'''

        content = f"""
        <div class="card">
            <h2>Projects</h2>
            <table>
                <tr><th>Name</th><th>Size</th><th>Modified</th></tr>
                {rows if rows else '<tr><td colspan="3" class="empty">No projects yet</td></tr>'}
            </table>
        </div>
        """
        self.send_html(html_page("Projects", content, "Projects"))

    def send_inbox(self):
        messages = get_inbox_messages()
        rows = ""
        for m in messages:
            content_preview = ""
            if isinstance(m.get("content"), dict):
                content_preview = html.escape(json.dumps(m["content"], ensure_ascii=False)[:100])
            rows += f'''<tr>
                <td>{make_file_link(m["path"], m["name"])}</td>
                <td><code>{content_preview}</code></td>
                <td>{m["modified"]}</td>
            </tr>'''

        content = f"""
        <div class="card">
            <h2>Inbox (External Messages)</h2>
            <p style="color: #8b949e; margin-bottom: 1rem;">Messages from human to agent</p>
            <table>
                <tr><th>File</th><th>Content</th><th>Modified</th></tr>
                {rows if rows else '<tr><td colspan="3" class="empty">Inbox empty</td></tr>'}
            </table>
        </div>
        """
        self.send_html(html_page("Inbox", content, "Inbox"))

    def send_outbox(self):
        messages = get_outbox_messages()
        rows = ""
        for m in messages:
            msg_type = m.get("type", "thought")
            badge_class = {"thought": "badge-blue", "poem": "badge-purple", "response": "badge-green"}.get(msg_type, "badge-blue")
            content_preview = html.escape(m.get("content", "")[:100])
            rows += f'''<tr>
                <td>{m.get("timestamp", "")[:19]}</td>
                <td>Session {m.get("session", "?")}</td>
                <td><span class="badge {badge_class}">{msg_type}</span></td>
                <td>{content_preview}...</td>
            </tr>'''

        content = f"""
        <div class="card">
            <h2>Outbox (Pending Messages)</h2>
            <p style="color: #8b949e; margin-bottom: 1rem;">Messages waiting to be sent to Telegram</p>
            <table>
                <tr><th>Time</th><th>Session</th><th>Type</th><th>Content</th></tr>
                {rows if rows else '<tr><td colspan="4" class="empty">Outbox empty</td></tr>'}
            </table>
        </div>
        """
        self.send_html(html_page("Outbox", content, "Outbox"))

    def send_api_logs(self, session_filter="", show_all=False):
        limit = 0 if show_all else 20
        files, total_count = get_api_logs_filtered(session_filter=session_filter or None, limit=limit)

        rows = ""
        for f in files:
            # Extract session number from filename
            session_num = ""
            if "session_" in f["name"]:
                parts = f["name"].split("_")
                if len(parts) >= 2:
                    session_num = parts[1]

            badge = "badge-green" if "output" in f["name"] else "badge-blue"
            rows += f'''<tr>
                <td>{make_file_link(f["path"], f["name"])}</td>
                <td><a href="/api-logs?session={session_num}">{session_num}</a></td>
                <td><span class="badge {badge}">{"response" if "output" in f["name"] else "request"}</span></td>
                <td>{f["size"]} bytes</td>
                <td>{f["modified"]}</td>
            </tr>'''

        # Build filter info
        filter_info = ""
        if session_filter:
            filter_info = f'for session <strong>{session_filter}</strong> (<a href="/api-logs">clear filter</a>)'
        showing_info = f"Showing {len(files)} of {total_count} files {filter_info}"

        content = f"""
        <div class="card" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
            <div>
                <span style="font-size: 1.5rem; color: #58a6ff; font-weight: bold;">{total_count}</span>
                <span style="color: #8b949e;"> total API log files</span>
            </div>
            <form action="/api-logs" method="get" style="display: flex; gap: 0.5rem; align-items: center;">
                <input type="text" name="session" placeholder="Session #" value="{html.escape(session_filter)}"
                    style="background: #0d1117; border: 1px solid #30363d; border-radius: 4px; padding: 0.4rem 0.8rem; color: #c9d1d9; width: 100px;">
                <button type="submit" style="background: #238636; border: none; border-radius: 4px; padding: 0.4rem 0.8rem; color: white; cursor: pointer;">Search</button>
                <a href="/api-logs?all=1" style="padding: 0.4rem 0.8rem; background: #21262d; border-radius: 4px; font-size: 0.9rem;">Show All</a>
            </form>
        </div>

        <div class="card">
            <h2>API Logs</h2>
            <p style="color: #8b949e; margin-bottom: 1rem;">{showing_info}</p>
            <table>
                <tr><th>File</th><th>Session</th><th>Type</th><th>Size</th><th>Time</th></tr>
                {rows if rows else '<tr><td colspan="5" class="empty">No API logs found</td></tr>'}
            </table>
        </div>
        """
        self.send_html(html_page("API Logs", content, "API Logs"))

    def send_core_log(self):
        log = html.escape(get_core_log(200))
        content = f"""
        <div class="card">
            <h2>Core Log (last 200 lines)</h2>
            <pre><code>{log}</code></pre>
        </div>
        """
        self.send_html(html_page("Core Log", content, "Core Log"))

    def send_security(self):
        log = html.escape(get_security_log())
        content = f"""
        <div class="card">
            <h2>Security Log</h2>
            <pre><code>{log}</code></pre>
        </div>
        """
        self.send_html(html_page("Security", content, "Security"))

    def send_file_view(self, filepath, raw=False):
        # Decode the path
        decoded_path = unquote(filepath)
        filename = Path(decoded_path).name if decoded_path else "Unknown"

        # Check if it's an API JSON file - show pretty format (unless raw requested)
        if not raw and decoded_path and "api" in decoded_path and filename.endswith(".json"):
            sections = format_api_json_pretty(decoded_path)
            if sections:
                sections_html = ""
                for title, content in sections:
                    sections_html += f'''
                    <div class="json-section">
                        <div class="json-section-header">{title}</div>
                        <div class="json-section-content">{content}</div>
                    </div>
                    '''
                content = f"""
                <style>
                    .json-section {{ margin-bottom: 1rem; border: 1px solid #30363d; border-radius: 6px; overflow: hidden; }}
                    .json-section-header {{ background: #21262d; padding: 0.5rem 1rem; font-size: 0.85rem; }}
                    .json-section-content {{ padding: 1rem; white-space: pre-wrap; word-wrap: break-word; font-family: 'Fira Code', Consolas, monospace; font-size: 0.85rem; background: #0d1117; }}
                    .section-title {{ font-weight: bold; }}
                    .role-system {{ color: #f59e0b; }}
                    .role-user {{ color: #3b82f6; }}
                    .role-assistant {{ color: #10b981; }}
                </style>
                <div class="card">
                    <h2>{html.escape(filename)}</h2>
                    <p style="color: #8b949e; margin-bottom: 1rem;">{html.escape(decoded_path)}</p>
                    <p style="margin-bottom: 1rem;"><a href="/file?path={quote(decoded_path, safe='')}&raw=1">View raw JSON</a></p>
                    {sections_html}
                </div>
                """
                self.send_html(html_page(filename, content, ""))
                return

        # Default: show raw content
        content_text = html.escape(read_file_safe(decoded_path))
        content = f"""
        <div class="card">
            <h2>{html.escape(filename)}</h2>
            <p style="color: #8b949e; margin-bottom: 1rem;">{html.escape(decoded_path)}</p>
            <pre><code>{content_text}</code></pre>
        </div>
        """
        self.send_html(html_page(filename, content, ""))


def main():
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"Dashboard running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
