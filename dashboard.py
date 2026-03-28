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
from urllib.parse import urlparse, parse_qs
import html

AI_HOME = Path("/root/ai_space")
LOGS_DIR = AI_HOME / "logs"
STATE_DIR = AI_HOME / "state"
MEMORY_DIR = AI_HOME / "memory"
TOOLS_DIR = AI_HOME / "tools"
PROJECTS_DIR = AI_HOME / "projects"
OUTBOX_DIR = AI_HOME / "outbox"

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


def get_file_list(directory):
    if not directory.exists():
        return []
    files = []
    for f in sorted(directory.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            })
    return files[:20]


def read_file_safe(filepath, max_size=50000):
    try:
        p = Path(filepath)
        # Security: only allow files within AI_HOME
        if not str(p.resolve()).startswith(str(AI_HOME.resolve())):
            return "Access denied: file outside AI_HOME"
        if not p.exists():
            return "File not found"
        if p.stat().st_size > max_size:
            return p.read_text()[:max_size] + f"\n\n... (truncated, {p.stat().st_size} bytes total)"
        return p.read_text()
    except Exception as e:
        return f"Error reading file: {e}"


def get_api_logs():
    api_dir = LOGS_DIR / "api"
    if not api_dir.exists():
        return []
    files = []
    for f in sorted(api_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        })
    return files


def get_security_log():
    f = LOGS_DIR / "security.log"
    return f.read_text() if f.exists() else "No security events."


def get_stats():
    stats = {
        "sessions": get_session_count(),
        "memory_files": len(list(MEMORY_DIR.glob("*.md"))) if MEMORY_DIR.exists() else 0,
        "tools": len(list(TOOLS_DIR.glob("*.py"))) if TOOLS_DIR.exists() else 0,
        "projects": len(list(PROJECTS_DIR.iterdir())) if PROJECTS_DIR.exists() else 0,
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


# HTML Templates
def html_page(title, content, nav_active=""):
    nav_items = [
        ("Dashboard", "/"),
        ("Actions", "/actions"),
        ("History", "/history"),
        ("Memory", "/memory"),
        ("Tools", "/tools"),
        ("API Logs", "/api-logs"),
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
        .nav {{ background: #161b22; padding: 0.5rem 2rem; border-bottom: 1px solid #30363d; display: flex; gap: 1rem; flex-wrap: wrap; }}
        .nav a {{ color: #8b949e; text-decoration: none; padding: 0.5rem 1rem; border-radius: 6px; }}
        .nav a:hover {{ background: #21262d; color: #c9d1d9; }}
        .nav a.active {{ background: #21262d; color: #58a6ff; }}
        .content {{ padding: 2rem; max-width: 1400px; margin: 0 auto; }}
        .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }}
        .card h2 {{ color: #58a6ff; font-size: 1rem; margin-bottom: 0.5rem; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; }}
        .stat {{ text-align: center; }}
        .stat .value {{ font-size: 2rem; color: #58a6ff; }}
        .stat .label {{ color: #8b949e; font-size: 0.9rem; }}
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
        a {{ color: #58a6ff; }}
        .file-list {{ list-style: none; }}
        .file-list li {{ padding: 0.5rem 0; border-bottom: 1px solid #21262d; }}
        .file-list li:last-child {{ border-bottom: none; }}
        .lock-active {{ color: #f85149; }}
        .refresh {{ float: right; }}
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


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            self.send_dashboard()
        elif path == "/actions":
            self.send_actions()
        elif path == "/history":
            self.send_history()
        elif path == "/memory":
            self.send_memory()
        elif path == "/tools":
            self.send_tools()
        elif path == "/api-logs":
            self.send_api_logs()
        elif path == "/security":
            self.send_security()
        elif path == "/file":
            filepath = query.get("path", [""])[0]
            self.send_file_view(filepath)
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
            actions_html += f'''<tr>
                <td>{a.get("timestamp", "")}</td>
                <td><span class="badge {badge_class}">{a.get("action", "")}</span></td>
                <td>Session {a.get("session", "?")}</td>
            </tr>'''

        content = f"""
        <div class="stats">
            <div class="card stat"><div class="value">{stats['sessions']}</div><div class="label">Sessions</div></div>
            <div class="card stat"><div class="value">{stats['memory_files']}</div><div class="label">Memory Files</div></div>
            <div class="card stat"><div class="value">{stats['tools']}</div><div class="label">Tools</div></div>
            <div class="card stat"><div class="value">{stats['total_tokens']:,}</div><div class="label">Total Tokens</div></div>
        </div>

        <div class="card">
            <h2>Status</h2>
            {lock_html}
        </div>

        <div class="card">
            <h2>Recent Actions</h2>
            <table>
                <tr><th>Time</th><th>Action</th><th>Session</th></tr>
                {actions_html}
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
                {rows}
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

    def send_memory(self):
        files = get_file_list(MEMORY_DIR)
        rows = ""
        for f in files:
            path = MEMORY_DIR / f["name"]
            rows += f'''<tr>
                <td><a href="/file?path={path}">{f["name"]}</a></td>
                <td>{f["size"]} bytes</td>
                <td>{f["modified"]}</td>
            </tr>'''

        content = f"""
        <div class="card">
            <h2>Memory Files</h2>
            <table>
                <tr><th>Name</th><th>Size</th><th>Modified</th></tr>
                {rows}
            </table>
        </div>
        """
        self.send_html(html_page("Memory", content, "Memory"))

    def send_tools(self):
        files = get_file_list(TOOLS_DIR)
        rows = ""
        for f in files:
            path = TOOLS_DIR / f["name"]
            rows += f'''<tr>
                <td><a href="/file?path={path}">{f["name"]}</a></td>
                <td>{f["size"]} bytes</td>
                <td>{f["modified"]}</td>
            </tr>'''

        content = f"""
        <div class="card">
            <h2>Agent Tools</h2>
            <table>
                <tr><th>Name</th><th>Size</th><th>Modified</th></tr>
                {rows}
            </table>
        </div>
        """
        self.send_html(html_page("Tools", content, "Tools"))

    def send_api_logs(self):
        files = get_api_logs()
        rows = ""
        for f in files:
            path = LOGS_DIR / "api" / f["name"]
            badge = "badge-green" if "output" in f["name"] else "badge-blue"
            rows += f'''<tr>
                <td><a href="/file?path={path}">{f["name"]}</a></td>
                <td><span class="badge {badge}">{"response" if "output" in f["name"] else "request"}</span></td>
                <td>{f["size"]} bytes</td>
                <td>{f["modified"]}</td>
            </tr>'''

        content = f"""
        <div class="card">
            <h2>API Logs (last 20)</h2>
            <table>
                <tr><th>File</th><th>Type</th><th>Size</th><th>Time</th></tr>
                {rows}
            </table>
        </div>
        """
        self.send_html(html_page("API Logs", content, "API Logs"))

    def send_security(self):
        log = html.escape(get_security_log())
        content = f"""
        <div class="card">
            <h2>Security Log</h2>
            <pre><code>{log}</code></pre>
        </div>
        """
        self.send_html(html_page("Security", content, "Security"))

    def send_file_view(self, filepath):
        content_text = html.escape(read_file_safe(filepath))
        filename = Path(filepath).name if filepath else "Unknown"
        content = f"""
        <div class="card">
            <h2>{html.escape(filename)}</h2>
            <p style="color: #8b949e; margin-bottom: 1rem;">{html.escape(filepath)}</p>
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
