# Eval Server Design

## Overview

A single-process FastHTML application (`mw eval-server`) that provides a web dashboard for submitting, monitoring, and reviewing MobileWorld evaluation jobs. It embeds the existing log viewer for detailed result inspection.

## Architecture

- **Web UI**: FastHTML + HTMX with 5s polling. Dashboard, job submission form, job detail with embedded log viewer, cancel support.
- **Background Worker**: Daemon thread polling SQLite job queue. Launches eval jobs via tmux sessions, manages Docker containers, cleans up on completion.
- **Storage**: SQLite (`jobs.db`) for job state. File-based traj logs (existing format).

```
FastHTML App (uvicorn, single port)
├── Web Routes (dashboard, submit, detail, logs, cancel)
├── Background Worker (daemon thread, polls queue)
└── SQLite DB (jobs.db)
```

## Data Model

```sql
CREATE TABLE jobs (
    id                TEXT PRIMARY KEY,
    label             TEXT,
    status            TEXT NOT NULL,  -- queued|running|completed|failed|cancelled
    agent_type        TEXT NOT NULL,
    model_name        TEXT NOT NULL,
    llm_base_url      TEXT NOT NULL,
    api_key           TEXT,
    env_count         INTEGER NOT NULL,
    max_round         INTEGER DEFAULT 50,
    step_wait_time    REAL DEFAULT 1.0,
    enable_user_interaction BOOLEAN DEFAULT FALSE,
    container_prefix  TEXT NOT NULL,
    log_dir           TEXT,
    tmux_session      TEXT,
    log_file          TEXT,
    total_tasks       INTEGER,
    successful_tasks  INTEGER,
    success_rate      REAL,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at        DATETIME,
    finished_at       DATETIME
);
```

## Pages

1. **Dashboard** (`/`) — job list table with status/score, docker count gauge, submit button
2. **Submit Job** (`/submit`) — form with agent_type dropdown, model URL, api key, env count, options
3. **Job Detail** (`/jobs/{id}`) — metadata, status, tmux log tail, embedded log viewer
4. **Cancel** (`POST /jobs/{id}/cancel`) — kills tmux session, removes containers, updates status

## Worker Logic

```
loop every 5s:
  for each "running" job:
    if tmux session exited:
      parse eval report → update results in DB
      run `mw env rm --all --prefix {prefix}`
      set status = completed|failed

  for each "queued" job (oldest first):
    current_containers = count running docker containers
    if current_containers + job.env_count <= MAX_CONTAINERS:
      run `mw env run --count {n} --mount_src --prefix {prefix}`
      launch tmux session with eval command, redirect to log file
      set status = running
```

## CLI

```bash
mw eval-server --port 8800 --max-containers 40
```

## Key Decisions

- Reuse existing log_viewer routes under `/jobs/{id}/logs/` prefix
- tmux sessions for job isolation + log capture
- No auth — optional label field for ownership
- Polling (5s HTMX) not WebSocket — matches existing log viewer pattern
- SQLite — lightweight, no external deps, sufficient for tens of jobs
