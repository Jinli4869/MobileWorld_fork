# Eval Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastHTML web dashboard (`mw eval-server`) for submitting, monitoring, and reviewing MobileWorld evaluation jobs with background worker-managed tmux sessions and Docker containers.

**Architecture:** Single-process FastHTML app with a daemon background worker thread. SQLite for job persistence. HTMX polling (5s) for live dashboard updates. Embeds existing log_viewer routes under `/jobs/{id}/logs/`. Worker manages eval jobs via tmux sessions, launches/cleans containers via CLI commands.

**Tech Stack:** FastHTML, HTMX, SQLite (stdlib `sqlite3`), uvicorn, tmux (subprocess), existing `mw` CLI for env/eval commands.

---

## File Structure

```
src/mobile_world/core/eval_server/
├── __init__.py          # Package init, exports main()
├── app.py               # FastHTML app creation, uvicorn launch, worker thread start
├── db.py                # SQLite schema, connection, CRUD operations
├── worker.py            # Background worker: queue processing, tmux, container lifecycle
├── routes.py            # Web routes: dashboard, submit, detail, cancel
├── styles.py            # CSS (extends log_viewer dark theme)
src/mobile_world/core/subcommands/
├── eval_server.py       # CLI subcommand: `mw eval-server`
src/mobile_world/core/subcommands/__init__.py  # (modify) Register new subcommand
src/mobile_world/core/cli.py                   # (modify) Add eval-server command
```

---

### Task 1: SQLite Database Module

**Files:**
- Create: `src/mobile_world/core/eval_server/__init__.py`
- Create: `src/mobile_world/core/eval_server/db.py`

- [ ] **Step 1: Create package init**

```python
# src/mobile_world/core/eval_server/__init__.py
"""Eval server — web dashboard for MobileWorld evaluation jobs."""
```

- [ ] **Step 2: Create db.py with schema and CRUD**

```python
# src/mobile_world/core/eval_server/db.py
"""SQLite database for eval job persistence."""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = None  # Set by app.py at startup


def _get_db_path() -> str:
    if DB_PATH is None:
        raise RuntimeError("DB_PATH not initialized — call init_db() first")
    return DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_dir: str = ".") -> None:
    global DB_PATH
    path = Path(db_dir) / "eval_jobs.db"
    DB_PATH = str(path)
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id                TEXT PRIMARY KEY,
            label             TEXT DEFAULT '',
            status            TEXT NOT NULL DEFAULT 'queued',
            agent_type        TEXT NOT NULL,
            model_name        TEXT NOT NULL,
            llm_base_url      TEXT NOT NULL,
            api_key           TEXT DEFAULT '',
            env_count         INTEGER NOT NULL,
            max_round         INTEGER DEFAULT 50,
            step_wait_time    REAL DEFAULT 1.0,
            enable_user_interaction INTEGER DEFAULT 0,
            container_prefix  TEXT NOT NULL,
            log_dir           TEXT DEFAULT '',
            tmux_session      TEXT DEFAULT '',
            log_file          TEXT DEFAULT '',
            total_tasks       INTEGER,
            successful_tasks  INTEGER,
            success_rate      REAL,
            created_at        TEXT DEFAULT (datetime('now')),
            started_at        TEXT,
            finished_at       TEXT
        )
    """)
    conn.commit()
    conn.close()


def create_job(
    agent_type: str,
    model_name: str,
    llm_base_url: str,
    env_count: int,
    api_key: str = "",
    label: str = "",
    max_round: int = 50,
    step_wait_time: float = 1.0,
    enable_user_interaction: bool = False,
) -> dict:
    job_id = uuid.uuid4().hex[:12]
    prefix = f"eval_{job_id}"
    conn = get_connection()
    conn.execute(
        """INSERT INTO jobs (id, label, agent_type, model_name, llm_base_url,
           api_key, env_count, max_round, step_wait_time,
           enable_user_interaction, container_prefix)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, label, agent_type, model_name, llm_base_url,
         api_key, env_count, max_round, step_wait_time,
         int(enable_user_interaction), prefix),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row)


def get_job(job_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_jobs(status: str | None = None) -> list[dict]:
    conn = get_connection()
    if status:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_job(job_id: str, **fields) -> None:
    conn = get_connection()
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [job_id]
    conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()


def count_running_envs() -> int:
    """Count total env_count across all running jobs."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(env_count), 0) as total FROM jobs WHERE status = 'running'"
    ).fetchone()
    conn.close()
    return row["total"]
```

- [ ] **Step 3: Verify module imports**

Run: `cd /Users/kongquyu/work/MobileWorld && uv run python -c "from mobile_world.core.eval_server.db import init_db, create_job, list_jobs; print('db module OK')"`
Expected: `db module OK`

- [ ] **Step 4: Commit**

```bash
git add src/mobile_world/core/eval_server/__init__.py src/mobile_world/core/eval_server/db.py
git commit -m "feat(eval-server): add SQLite database module for job persistence"
```

---

### Task 2: Background Worker

**Files:**
- Create: `src/mobile_world/core/eval_server/worker.py`

- [ ] **Step 1: Create worker.py**

```python
# src/mobile_world/core/eval_server/worker.py
"""Background worker for processing eval job queue."""

import os
import json
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from loguru import logger

from mobile_world.core.eval_server import db

MAX_CONTAINERS = 40  # Default, overridden by CLI arg
POLL_INTERVAL = 5    # seconds
LOG_BASE_DIR = "eval_server_logs"


def _tmux_session_exists(session_name: str) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True,
    )
    return result.returncode == 0


def _count_docker_containers() -> int:
    """Count running MobileWorld Docker containers."""
    result = subprocess.run(
        ["docker", "ps", "--filter", "ancestor=mobile_world", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.warning("Failed to count docker containers: {}", result.stderr)
        return 0
    lines = [l for l in result.stdout.strip().split("\n") if l]
    return len(lines)


def _start_job(job: dict) -> None:
    """Launch containers and start eval in a tmux session."""
    job_id = job["id"]
    prefix = job["container_prefix"]
    env_count = job["env_count"]
    log_dir = os.path.join(LOG_BASE_DIR, f"job_{job_id}")
    os.makedirs(log_dir, exist_ok=True)

    tmux_session = f"eval_{job_id}"
    log_file = os.path.join(log_dir, "output.log")
    traj_log_dir = os.path.join(log_dir, "traj_logs")

    # Build the eval command
    eval_cmd_parts = [
        "uv", "run", "mw", "eval",
        "--agent-type", job["agent_type"],
        "--tasks", "ALL",
        "--max-round", str(job["max_round"]),
        "--model-name", job["model_name"],
        "--llm-base-url", job["llm_base_url"],
        "--step-wait-time", str(job["step_wait_time"]),
        "--log-file-root", traj_log_dir,
        "--env-prefix", prefix,
    ]
    if job.get("api_key"):
        eval_cmd_parts.extend(["--api-key", job["api_key"]])
    if job.get("enable_user_interaction"):
        eval_cmd_parts.append("--enable-user-interaction")

    eval_cmd = " ".join(eval_cmd_parts)

    # Combined command: launch containers, then run eval
    env_cmd = f"uv run mw env run --count {env_count} --mount-src --name-prefix {prefix}"
    full_cmd = f"{env_cmd} && {eval_cmd}"

    # Launch in tmux session, redirect output
    tmux_cmd = [
        "tmux", "new-session", "-d", "-s", tmux_session,
        f"bash -c '{full_cmd}' 2>&1 | tee {log_file}",
    ]

    logger.info("Starting job {}: tmux session={}, prefix={}", job_id, tmux_session, prefix)
    subprocess.run(tmux_cmd, check=True)

    db.update_job(
        job_id,
        status="running",
        started_at=datetime.now().isoformat(),
        tmux_session=tmux_session,
        log_file=log_file,
        log_dir=traj_log_dir,
    )


def _cleanup_containers(prefix: str) -> None:
    """Remove containers with the given prefix."""
    cmd = ["uv", "run", "mw", "env", "rm", "--all", "--name-prefix", prefix]
    logger.info("Cleaning up containers with prefix: {}", prefix)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("Container cleanup warning: {}", result.stderr)


def _parse_eval_results(log_dir: str) -> dict:
    """Parse eval report JSON from the traj log directory."""
    results = {"total_tasks": None, "successful_tasks": None, "success_rate": None}
    if not log_dir or not os.path.isdir(log_dir):
        return results

    # Find eval_report_*.json files
    report_files = sorted(Path(log_dir).glob("eval_report_*.json"), reverse=True)
    if not report_files:
        return results

    try:
        with open(report_files[0]) as f:
            report = json.load(f)
        summary = report.get("summary", {})
        results["total_tasks"] = summary.get("total_tasks_with_results")
        results["successful_tasks"] = summary.get("successful_tasks")
        results["success_rate"] = summary.get("overall_success_rate")
    except Exception as e:
        logger.warning("Failed to parse eval report {}: {}", report_files[0], e)

    return results


def _check_running_jobs() -> None:
    """Check if any running jobs have finished."""
    running_jobs = db.list_jobs(status="running")
    for job in running_jobs:
        tmux_session = job.get("tmux_session", "")
        if not tmux_session:
            continue

        if not _tmux_session_exists(tmux_session):
            # Session ended — job finished
            logger.info("Job {} tmux session ended, collecting results", job["id"])

            results = _parse_eval_results(job.get("log_dir", ""))
            _cleanup_containers(job["container_prefix"])

            # Determine final status
            status = "completed" if results.get("total_tasks") else "failed"

            db.update_job(
                job["id"],
                status=status,
                finished_at=datetime.now().isoformat(),
                **results,
            )
            logger.info("Job {} finished with status={}", job["id"], status)


def _process_queue(max_containers: int) -> None:
    """Try to start queued jobs if capacity allows."""
    queued_jobs = db.list_jobs(status="queued")
    if not queued_jobs:
        return

    current_containers = _count_docker_containers()

    for job in queued_jobs:
        if current_containers + job["env_count"] <= max_containers:
            try:
                _start_job(job)
                current_containers += job["env_count"]
            except Exception as e:
                logger.error("Failed to start job {}: {}", job["id"], e)
                db.update_job(job["id"], status="failed",
                              finished_at=datetime.now().isoformat())


def cancel_job(job_id: str) -> bool:
    """Cancel a running or queued job."""
    job = db.get_job(job_id)
    if not job:
        return False

    if job["status"] == "queued":
        db.update_job(job_id, status="cancelled",
                      finished_at=datetime.now().isoformat())
        return True

    if job["status"] == "running":
        # Kill tmux session
        tmux_session = job.get("tmux_session", "")
        if tmux_session:
            subprocess.run(
                ["tmux", "kill-session", "-t", tmux_session],
                capture_output=True,
            )
        # Cleanup containers
        _cleanup_containers(job["container_prefix"])

        db.update_job(job_id, status="cancelled",
                      finished_at=datetime.now().isoformat())
        return True

    return False


def worker_loop(max_containers: int = MAX_CONTAINERS) -> None:
    """Main worker loop — runs in a daemon thread."""
    logger.info("Eval worker started (max_containers={})", max_containers)
    while True:
        try:
            _check_running_jobs()
            _process_queue(max_containers)
        except Exception as e:
            logger.error("Worker loop error: {}", e)
        time.sleep(POLL_INTERVAL)


def start_worker(max_containers: int = MAX_CONTAINERS) -> threading.Thread:
    """Start the background worker thread."""
    thread = threading.Thread(
        target=worker_loop,
        args=(max_containers,),
        daemon=True,
        name="eval-worker",
    )
    thread.start()
    return thread
```

- [ ] **Step 2: Verify module imports**

Run: `cd /Users/kongquyu/work/MobileWorld && uv run python -c "from mobile_world.core.eval_server.worker import start_worker, cancel_job; print('worker module OK')"`
Expected: `worker module OK`

- [ ] **Step 3: Commit**

```bash
git add src/mobile_world/core/eval_server/worker.py
git commit -m "feat(eval-server): add background worker for job queue processing"
```

---

### Task 3: Styles

**Files:**
- Create: `src/mobile_world/core/eval_server/styles.py`

- [ ] **Step 1: Create styles.py extending the log_viewer dark theme**

```python
# src/mobile_world/core/eval_server/styles.py
"""CSS styles for the eval server dashboard."""

EVAL_SERVER_CSS = """
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --text-primary: #c9d1d9;
    --text-secondary: #8b949e;
    --accent-color: #58a6ff;
    --success-color: #3fb950;
    --warning-color: #d29922;
    --danger-color: #f85149;
    --border-color: #30363d;
    --shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background-color: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.5;
}

.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
}

/* Header */
.app-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 24px;
    border-radius: 8px;
}

.app-header h1 {
    font-size: 20px;
    font-weight: 600;
}

/* Stats cards row */
.stats-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}

.stat-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
    text-align: center;
}

.stat-card .stat-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--accent-color);
}

.stat-card .stat-label {
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
}

/* Status badges */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}
.badge-queued { background: #30363d; color: #8b949e; }
.badge-running { background: #0d419d; color: #58a6ff; }
.badge-completed { background: #0f5323; color: #3fb950; }
.badge-failed { background: #67060c; color: #f85149; }
.badge-cancelled { background: #3d2e00; color: #d29922; }

/* Job table */
.job-table {
    width: 100%;
    border-collapse: collapse;
    background: var(--bg-secondary);
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border-color);
}

.job-table th {
    background: var(--bg-tertiary);
    padding: 12px 16px;
    text-align: left;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border-color);
}

.job-table td {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    font-size: 14px;
}

.job-table tr:hover {
    background: var(--bg-tertiary);
}

.job-table tr:last-child td {
    border-bottom: none;
}

/* Forms */
.form-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 24px;
    margin-bottom: 24px;
}

.form-card h2 {
    font-size: 16px;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color);
}

.form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.form-group.full-width {
    grid-column: 1 / -1;
}

.form-group label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
}

.form-group input,
.form-group select {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 8px 12px;
    color: var(--text-primary);
    font-size: 14px;
}

.form-group input:focus,
.form-group select:focus {
    outline: none;
    border-color: var(--accent-color);
    box-shadow: 0 0 0 2px rgba(88, 166, 255, 0.2);
}

/* Buttons */
.btn {
    padding: 8px 20px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.2s;
}

.btn:hover { opacity: 0.85; }

.btn-primary {
    background: var(--accent-color);
    color: #fff;
}

.btn-danger {
    background: var(--danger-color);
    color: #fff;
}

.btn-sm {
    padding: 4px 12px;
    font-size: 12px;
}

/* Job detail */
.detail-header {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 24px;
}

.detail-meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
    margin-top: 12px;
}

.detail-meta dt {
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
}

.detail-meta dd {
    font-size: 14px;
    margin: 0 0 8px 0;
}

/* Log output */
.log-output {
    background: #010409;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 500px;
    overflow-y: auto;
    color: var(--text-primary);
}

/* Checkbox as toggle */
.toggle-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 14px;
}

.toggle-label input[type="checkbox"] {
    width: 16px;
    height: 16px;
    accent-color: var(--accent-color);
}

/* Responsive */
@media (max-width: 768px) {
    .form-grid { grid-template-columns: 1fr; }
    .stats-row { grid-template-columns: 1fr 1fr; }
}

/* Links */
a {
    color: var(--accent-color);
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
}

/* Flash messages */
.flash-success {
    background: #0f5323;
    color: #3fb950;
    border: 1px solid #238636;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 16px;
}

.flash-error {
    background: #67060c;
    color: #f85149;
    border: 1px solid #da3633;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 16px;
}
"""
```

- [ ] **Step 2: Commit**

```bash
git add src/mobile_world/core/eval_server/styles.py
git commit -m "feat(eval-server): add dark theme CSS for dashboard"
```

---

### Task 4: Web Routes

**Files:**
- Create: `src/mobile_world/core/eval_server/routes.py`

- [ ] **Step 1: Create routes.py with dashboard, submit, detail, cancel, and log viewer embedding**

```python
# src/mobile_world/core/eval_server/routes.py
"""Route handlers for the eval server dashboard."""

import os
from urllib.parse import quote

from fasthtml.common import *  # noqa: F403
from loguru import logger

from mobile_world.agents.registry import AGENT_CONFIGS
from mobile_world.core.eval_server import db
from mobile_world.core.eval_server.styles import EVAL_SERVER_CSS
from mobile_world.core.eval_server.worker import cancel_job


def register_routes(rt):
    """Register all eval server routes."""

    agent_types = list(AGENT_CONFIGS.keys())

    def _status_badge(status: str):
        return Span(status, cls=f"badge badge-{status}")

    def _page_shell(*content, title="Eval Server"):
        return (
            Title(title),
            Style(EVAL_SERVER_CSS),
            Div(
                Div(
                    H1("MobileWorld Eval Server"),
                    Div(
                        A("Dashboard", href="/", cls="btn btn-sm btn-primary",
                          style="margin-right: 8px;"),
                        A("Submit Job", href="/submit", cls="btn btn-sm btn-primary"),
                    ),
                    cls="app-header",
                ),
                *content,
                cls="container",
            ),
        )

    # ── Dashboard ────────────────────────────────────────────

    @rt("/")
    def dashboard():
        jobs = db.list_jobs()
        running_jobs = [j for j in jobs if j["status"] == "running"]
        running_envs = sum(j["env_count"] for j in running_jobs)
        completed_jobs = [j for j in jobs if j["status"] == "completed"]
        failed_jobs = [j for j in jobs if j["status"] == "failed"]

        stats = Div(
            Div(Div(str(len(jobs)), cls="stat-value"),
                Div("Total Jobs", cls="stat-label"), cls="stat-card"),
            Div(Div(str(len(running_jobs)), cls="stat-value"),
                Div("Running", cls="stat-label"), cls="stat-card"),
            Div(Div(str(len(completed_jobs)), cls="stat-value"),
                Div("Completed", cls="stat-label"), cls="stat-card"),
            Div(Div(str(len(failed_jobs)), cls="stat-value"),
                Div("Failed", cls="stat-label"), cls="stat-card"),
            Div(Div(str(running_envs), cls="stat-value"),
                Div("Running Envs", cls="stat-label"), cls="stat-card"),
            cls="stats-row",
            id="stats-row",
        )

        # Job table
        rows = []
        for j in jobs:
            score_text = ""
            if j.get("success_rate") is not None:
                score_text = f"{j['success_rate']:.1%} ({j['successful_tasks']}/{j['total_tasks']})"

            actions = ""
            if j["status"] in ("queued", "running"):
                actions = Form(
                    Button("Cancel", cls="btn btn-danger btn-sm", type="submit"),
                    method="post",
                    action=f"/jobs/{j['id']}/cancel",
                )

            rows.append(Tr(
                Td(A(j["id"][:8], href=f"/jobs/{j['id']}")),
                Td(j.get("label") or "-"),
                Td(_status_badge(j["status"])),
                Td(j["agent_type"]),
                Td(j["model_name"]),
                Td(str(j["env_count"])),
                Td(score_text or "-"),
                Td(j.get("created_at", "")[:16]),
                Td(actions),
            ))

        table = Table(
            Thead(Tr(
                Th("ID"), Th("Label"), Th("Status"), Th("Agent"),
                Th("Model"), Th("Envs"), Th("Score"), Th("Created"), Th("Actions"),
            )),
            Tbody(*rows),
            cls="job-table",
        )

        # Wrap dashboard content for HTMX polling
        dashboard_content = Div(
            stats, table,
            id="dashboard-content",
            hx_get="/dashboard-content",
            hx_trigger="every 5s",
            hx_swap="outerHTML",
        )

        return _page_shell(dashboard_content)

    @rt("/dashboard-content")
    def dashboard_content():
        """HTMX partial for dashboard polling."""
        jobs = db.list_jobs()
        running_jobs = [j for j in jobs if j["status"] == "running"]
        running_envs = sum(j["env_count"] for j in running_jobs)
        completed_jobs = [j for j in jobs if j["status"] == "completed"]
        failed_jobs = [j for j in jobs if j["status"] == "failed"]

        stats = Div(
            Div(Div(str(len(jobs)), cls="stat-value"),
                Div("Total Jobs", cls="stat-label"), cls="stat-card"),
            Div(Div(str(len(running_jobs)), cls="stat-value"),
                Div("Running", cls="stat-label"), cls="stat-card"),
            Div(Div(str(len(completed_jobs)), cls="stat-value"),
                Div("Completed", cls="stat-label"), cls="stat-card"),
            Div(Div(str(len(failed_jobs)), cls="stat-value"),
                Div("Failed", cls="stat-label"), cls="stat-card"),
            Div(Div(str(running_envs), cls="stat-value"),
                Div("Running Envs", cls="stat-label"), cls="stat-card"),
            cls="stats-row",
        )

        rows = []
        for j in jobs:
            score_text = ""
            if j.get("success_rate") is not None:
                score_text = f"{j['success_rate']:.1%} ({j['successful_tasks']}/{j['total_tasks']})"

            actions = ""
            if j["status"] in ("queued", "running"):
                actions = Form(
                    Button("Cancel", cls="btn btn-danger btn-sm", type="submit"),
                    method="post",
                    action=f"/jobs/{j['id']}/cancel",
                )

            rows.append(Tr(
                Td(A(j["id"][:8], href=f"/jobs/{j['id']}")),
                Td(j.get("label") or "-"),
                Td(_status_badge(j["status"])),
                Td(j["agent_type"]),
                Td(j["model_name"]),
                Td(str(j["env_count"])),
                Td(score_text or "-"),
                Td(j.get("created_at", "")[:16]),
                Td(actions),
            ))

        table = Table(
            Thead(Tr(
                Th("ID"), Th("Label"), Th("Status"), Th("Agent"),
                Th("Model"), Th("Envs"), Th("Score"), Th("Created"), Th("Actions"),
            )),
            Tbody(*rows),
            cls="job-table",
        )

        return Div(
            stats, table,
            id="dashboard-content",
            hx_get="/dashboard-content",
            hx_trigger="every 5s",
            hx_swap="outerHTML",
        )

    # ── Submit Job ───────────────────────────────────────────

    @rt("/submit")
    def submit_form():
        agent_options = [Option(name, value=name) for name in agent_types]

        form = Div(
            H2("Submit Evaluation Job"),
            Form(
                Div(
                    Div(
                        Label("Label (optional)"),
                        Input(name="label", placeholder="e.g. your name or experiment tag"),
                        cls="form-group",
                    ),
                    Div(
                        Label("Agent Type"),
                        Select(*agent_options, name="agent_type"),
                        cls="form-group",
                    ),
                    Div(
                        Label("Model Name"),
                        Input(name="model_name", required=True,
                              placeholder="e.g. gui-32b-0403-V8d1"),
                        cls="form-group",
                    ),
                    Div(
                        Label("LLM Base URL"),
                        Input(name="llm_base_url", required=True,
                              placeholder="http://..."),
                        cls="form-group",
                    ),
                    Div(
                        Label("API Key (optional, falls back to .env)"),
                        Input(name="api_key", type="password",
                              placeholder="Leave empty to use .env"),
                        cls="form-group",
                    ),
                    Div(
                        Label("Number of Environments"),
                        Input(name="env_count", type="number", value="5",
                              min="1", max="40", required=True),
                        cls="form-group",
                    ),
                    Div(
                        Label("Max Rounds"),
                        Input(name="max_round", type="number", value="50",
                              min="1"),
                        cls="form-group",
                    ),
                    Div(
                        Label("Step Wait Time (seconds)"),
                        Input(name="step_wait_time", type="number", value="3",
                              min="0.1", step="0.1"),
                        cls="form-group",
                    ),
                    Div(
                        Label(
                            Input(type="checkbox", name="enable_user_interaction"),
                            " Enable User Interaction Tasks",
                            cls="toggle-label",
                        ),
                        cls="form-group",
                    ),
                    cls="form-grid",
                ),
                Div(
                    Button("Submit Job", type="submit", cls="btn btn-primary"),
                    style="margin-top: 20px; text-align: right;",
                ),
                method="post",
                action="/submit",
            ),
            cls="form-card",
        )

        return _page_shell(form, title="Submit Job - Eval Server")

    @rt("/submit", methods=["POST"])
    async def submit_job(request):
        form = await request.form()
        job = db.create_job(
            agent_type=form["agent_type"],
            model_name=form["model_name"],
            llm_base_url=form["llm_base_url"],
            env_count=int(form["env_count"]),
            api_key=form.get("api_key", ""),
            label=form.get("label", ""),
            max_round=int(form.get("max_round", 50)),
            step_wait_time=float(form.get("step_wait_time", 1.0)),
            enable_user_interaction=form.get("enable_user_interaction") == "on",
        )
        return RedirectResponse(f"/jobs/{job['id']}", status_code=303)

    # ── Job Detail ───────────────────────────────────────────

    @rt("/jobs/{job_id}")
    def job_detail(job_id: str):
        job = db.get_job(job_id)
        if not job:
            return _page_shell(Div("Job not found", cls="flash-error"))

        # Metadata
        meta_items = [
            ("Status", _status_badge(job["status"])),
            ("Agent Type", job["agent_type"]),
            ("Model", job["model_name"]),
            ("LLM URL", job["llm_base_url"]),
            ("Envs", str(job["env_count"])),
            ("Max Rounds", str(job["max_round"])),
            ("Step Wait", f"{job['step_wait_time']}s"),
            ("User Interaction", "Yes" if job["enable_user_interaction"] else "No"),
            ("Created", job.get("created_at", "")),
            ("Started", job.get("started_at", "") or "-"),
            ("Finished", job.get("finished_at", "") or "-"),
            ("Label", job.get("label") or "-"),
        ]

        meta_dl = Dl(
            *[item for dt_text, dd_val in meta_items
              for item in (Dt(dt_text), Dd(dd_val))],
            cls="detail-meta",
        )

        # Results section
        results_section = ""
        if job.get("success_rate") is not None:
            results_section = Div(
                H3("Results"),
                Div(
                    Div(Div(f"{job['success_rate']:.1%}", cls="stat-value"),
                        Div("Success Rate", cls="stat-label"), cls="stat-card"),
                    Div(Div(str(job["successful_tasks"]), cls="stat-value"),
                        Div("Successful", cls="stat-label"), cls="stat-card"),
                    Div(Div(str(job["total_tasks"]), cls="stat-value"),
                        Div("Total Tasks", cls="stat-label"), cls="stat-card"),
                    cls="stats-row",
                ),
                style="margin-bottom: 24px;",
            )

        # Cancel button
        cancel_btn = ""
        if job["status"] in ("queued", "running"):
            cancel_btn = Form(
                Button("Cancel Job", cls="btn btn-danger", type="submit"),
                method="post",
                action=f"/jobs/{job_id}/cancel",
                style="margin-bottom: 24px;",
            )

        # Log output section (polls for updates)
        log_section = Div(
            H3("Output Log"),
            Div(
                _read_log_tail(job.get("log_file", ""), 200),
                cls="log-output",
                id="log-output",
                hx_get=f"/jobs/{job_id}/log-tail",
                hx_trigger="every 5s" if job["status"] == "running" else None,
                hx_swap="innerHTML",
            ),
            style="margin-bottom: 24px;",
        )

        # Link to embedded log viewer
        log_viewer_link = ""
        log_dir = job.get("log_dir", "")
        if log_dir and os.path.isdir(log_dir):
            log_viewer_link = Div(
                A(
                    "Open Full Log Viewer",
                    href=f"/jobs/{job_id}/logs/?log_root={quote(os.path.abspath(log_dir))}",
                    cls="btn btn-primary",
                ),
                style="margin-bottom: 24px;",
            )

        header = Div(
            Div(
                H2(f"Job {job_id[:8]}"),
                meta_dl,
                cls="detail-header",
            ),
            cancel_btn,
            results_section,
            log_viewer_link,
            log_section,
        )

        return _page_shell(header, title=f"Job {job_id[:8]} - Eval Server")

    @rt("/jobs/{job_id}/log-tail")
    def job_log_tail(job_id: str):
        job = db.get_job(job_id)
        if not job:
            return Pre("Job not found")
        return _read_log_tail(job.get("log_file", ""), 200)

    # ── Cancel ───────────────────────────────────────────────

    @rt("/jobs/{job_id}/cancel", methods=["POST"])
    def job_cancel(job_id: str):
        cancel_job(job_id)
        return RedirectResponse(f"/jobs/{job_id}", status_code=303)

    # ── Log Viewer Embedding ─────────────────────────────────

    from mobile_world.core.log_viewer.routes import register_routes as register_log_viewer_routes

    # We register the log viewer routes for each job access dynamically
    # via a catch-all that sets log_root and forwards
    @rt("/jobs/{job_id}/logs/{path:path}")
    def job_logs(job_id: str, path: str, request):
        job = db.get_job(job_id)
        if not job:
            return _page_shell(Div("Job not found", cls="flash-error"))

        log_dir = job.get("log_dir", "")
        if not log_dir or not os.path.isdir(log_dir):
            return _page_shell(Div("Log directory not available yet", cls="flash-error"))

        # Set the log root for the log viewer
        from mobile_world.core.log_viewer.utils import get_log_root_state
        state = get_log_root_state()
        state["log_root"] = os.path.abspath(log_dir)

        # Redirect to the main log viewer with base path
        # The log viewer routes are registered separately
        return RedirectResponse(
            f"/log-viewer/?log_root={quote(os.path.abspath(log_dir))}",
            status_code=302,
        )


def _read_log_tail(log_file: str, lines: int = 200) -> str:
    """Read the last N lines from a log file."""
    if not log_file or not os.path.isfile(log_file):
        return "No log output yet."
    try:
        with open(log_file) as f:
            all_lines = f.readlines()
        return "".join(all_lines[-lines:])
    except Exception as e:
        return f"Error reading log: {e}"
```

- [ ] **Step 2: Verify module imports**

Run: `cd /Users/kongquyu/work/MobileWorld && uv run python -c "from mobile_world.core.eval_server.routes import register_routes; print('routes module OK')"`
Expected: `routes module OK`

- [ ] **Step 3: Commit**

```bash
git add src/mobile_world/core/eval_server/routes.py
git commit -m "feat(eval-server): add FastHTML routes for dashboard, submit, detail, cancel"
```

---

### Task 5: App Entry Point

**Files:**
- Modify: `src/mobile_world/core/eval_server/__init__.py`
- Create: `src/mobile_world/core/eval_server/app.py`

- [ ] **Step 1: Create app.py**

```python
# src/mobile_world/core/eval_server/app.py
"""Main FastHTML application for eval server."""

import warnings

import uvicorn
from fasthtml.common import fast_app
from loguru import logger

from mobile_world.core.eval_server import db
from mobile_world.core.eval_server.routes import register_routes
from mobile_world.core.eval_server.worker import start_worker
from mobile_world.core.log_viewer.routes import register_routes as register_log_viewer_routes

warnings.filterwarnings("ignore", message="'audioop' is deprecated", category=DeprecationWarning)

app, rt = fast_app()


def main(
    port: int = 8800,
    max_containers: int = 40,
    data_dir: str = ".",
):
    """Launch the eval server."""
    # Initialize database
    db.init_db(db_dir=data_dir)
    logger.info("Database initialized at {}/eval_jobs.db", data_dir)

    # Register eval server routes
    register_routes(rt)

    # Register log viewer routes under /log-viewer/ prefix
    register_log_viewer_routes(rt, base_path="/log-viewer/")

    # Start background worker
    start_worker(max_containers=max_containers)
    logger.info("Background worker started (max_containers={})", max_containers)

    logger.info("Eval server starting at http://0.0.0.0:{}", port)
    print(f"Link: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False, ws="none")
```

- [ ] **Step 2: Update __init__.py to export main**

Replace the content of `src/mobile_world/core/eval_server/__init__.py` with:

```python
"""Eval server — web dashboard for MobileWorld evaluation jobs."""

from mobile_world.core.eval_server.app import main

__all__ = ["main"]
```

- [ ] **Step 3: Verify app imports**

Run: `cd /Users/kongquyu/work/MobileWorld && uv run python -c "from mobile_world.core.eval_server.app import main; print('app module OK')"`
Expected: `app module OK`

- [ ] **Step 4: Commit**

```bash
git add src/mobile_world/core/eval_server/app.py src/mobile_world/core/eval_server/__init__.py
git commit -m "feat(eval-server): add FastHTML app entry point with worker startup"
```

---

### Task 6: CLI Subcommand Registration

**Files:**
- Create: `src/mobile_world/core/subcommands/eval_server.py`
- Modify: `src/mobile_world/core/subcommands/__init__.py`
- Modify: `src/mobile_world/core/cli.py`

- [ ] **Step 1: Create eval_server.py subcommand**

```python
# src/mobile_world/core/subcommands/eval_server.py
"""Eval server subcommand for MobileWorld CLI."""

import argparse


def configure_parser(subparsers: argparse._SubParsersAction) -> None:
    """Configure the eval-server subcommand parser."""
    parser = subparsers.add_parser(
        "eval-server",
        help="Launch the evaluation server dashboard",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8800,
        help="Server port (default: 8800)",
    )
    parser.add_argument(
        "--max-containers",
        "--max_containers",
        dest="max_containers",
        type=int,
        default=40,
        help="Maximum number of Docker containers allowed (default: 40)",
    )
    parser.add_argument(
        "--data-dir",
        "--data_dir",
        dest="data_dir",
        default=".",
        help="Directory for database and logs (default: current directory)",
    )


async def execute(args: argparse.Namespace) -> None:
    """Execute the eval-server command."""
    from mobile_world.core.eval_server.app import main

    main(
        port=args.port,
        max_containers=args.max_containers,
        data_dir=args.data_dir,
    )
```

- [ ] **Step 2: Register in subcommands/__init__.py**

Add to `src/mobile_world/core/subcommands/__init__.py`:

After the existing imports, add:
```python
from .eval_server import configure_parser as configure_eval_server_parser
from .eval_server import execute as execute_eval_server
```

Add to `__all__`:
```python
"configure_eval_server_parser",
"execute_eval_server",
```

- [ ] **Step 3: Register in cli.py**

In `src/mobile_world/core/cli.py`:

In `create_parser()`, after `subcommands.configure_info_parser(subparsers)`, add:
```python
    subcommands.configure_eval_server_parser(subparsers)
```

In `async_main()`, before the `else:` block, add:
```python
    elif args.command == "eval-server":
        await subcommands.execute_eval_server(args)
```

- [ ] **Step 4: Verify CLI registration**

Run: `cd /Users/kongquyu/work/MobileWorld && uv run mw eval-server --help`
Expected: Shows help with `--port`, `--max-containers`, `--data-dir` options

- [ ] **Step 5: Commit**

```bash
git add src/mobile_world/core/subcommands/eval_server.py src/mobile_world/core/subcommands/__init__.py src/mobile_world/core/cli.py
git commit -m "feat(eval-server): register eval-server CLI subcommand"
```

---

### Task 7: Integration Test — End-to-End Smoke Test

**Files:**
- No new files — manual verification

- [ ] **Step 1: Start the eval server**

Run: `cd /Users/kongquyu/work/MobileWorld && uv run mw eval-server --port 8800 --data-dir /tmp/eval_test`
Expected: Server starts, prints `Link: http://localhost:8800`, worker starts

- [ ] **Step 2: Verify dashboard loads**

Open `http://localhost:8800` in browser — should see empty dashboard with stats (all zeros) and empty job table.

- [ ] **Step 3: Verify submit form loads**

Open `http://localhost:8800/submit` — should see form with agent type dropdown, model name, URL, etc.

- [ ] **Step 4: Verify database created**

Run: `ls /tmp/eval_test/eval_jobs.db`
Expected: File exists

- [ ] **Step 5: Stop server and commit any fixes**

```bash
# If any fixes were needed:
git add -A
git commit -m "fix(eval-server): integration test fixes"
```

---

Plan complete and saved to `docs/superpowers/plans/2026-04-10-eval-server.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?