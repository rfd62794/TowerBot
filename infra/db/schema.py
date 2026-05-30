"""DB schema, connection, and shared primitives."""
# SCHEMA RULE: All table creation and migrations belong in init_db() only.
# Never run SQL at module import time — _conn is None until init_db() is
# called from privybot.py startup.
# TIMESTAMP FORMAT RULE: Always use datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# for timestamps written to SQLite. SQLite CURRENT_TIMESTAMP uses space separator.
# Python's datetime.isoformat() uses T separator. Mixing them breaks datetime
# comparisons. strftime format is the standard for this codebase.

import os
import sqlite3
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "privy.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    name TEXT,
    created DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT,
    role TEXT,
    content TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (thread_id) REFERENCES threads(id)
);

CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE,
    content TEXT,
    layer TEXT,
    created DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS model_status (
    model_id TEXT PRIMARY KEY,
    last_429 DATETIME,
    retry_after_seconds REAL DEFAULT 60,
    fail_count INTEGER DEFAULT 0,
    last_success DATETIME,
    last_checked DATETIME
);

CREATE TABLE IF NOT EXISTS kv_cache (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tool_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT,
    params_hash TEXT,
    result TEXT,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tool_cache ON tool_cache(tool_name, params_hash);

CREATE TABLE IF NOT EXISTS preload_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT NOT NULL,
    params_hash TEXT,
    fetched_at TEXT NOT NULL,
    success INTEGER DEFAULT 0,
    duration_ms INTEGER,
    error_msg TEXT
);

CREATE INDEX IF NOT EXISTS idx_preload_log_tool ON preload_log(tool_name, fetched_at DESC);

CREATE TABLE IF NOT EXISTS channel_history (
    date TEXT PRIMARY KEY,
    views INTEGER,
    watch_time_minutes REAL,
    subscribers_gained INTEGER,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS video_history (
    video_id TEXT,
    date TEXT,
    views INTEGER,
    watch_time_minutes REAL,
    avg_view_duration_seconds REAL,
    avg_view_percentage REAL,
    PRIMARY KEY (video_id, date)
);

CREATE TABLE IF NOT EXISTS game_history (
    appid INTEGER,
    date TEXT,
    players_2weeks INTEGER,
    owners_low INTEGER,
    owners_high INTEGER,
    price_usd REAL,
    on_sale INTEGER,
    PRIMARY KEY (appid, date)
);

CREATE TABLE IF NOT EXISTS weather_history (
    date TEXT PRIMARY KEY,
    temp_f REAL,
    condition TEXT,
    wind_mph REAL,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS video_metadata_cache (
    video_id TEXT PRIMARY KEY,
    title TEXT,
    description TEXT,
    tags TEXT,
    duration_seconds INTEGER,
    published_at TEXT,
    thumbnail_url TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduled_videos (
    video_id TEXT PRIMARY KEY,
    title TEXT,
    scheduled_time DATETIME,
    privacy_status TEXT,
    last_checked DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT,
    message TEXT,
    priority TEXT DEFAULT 'normal',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    scheduled_for DATETIME,
    sent INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    title TEXT,
    description TEXT,
    deadline TEXT,
    status TEXT DEFAULT 'active',
    progress_pct INTEGER DEFAULT 0,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS milestones (
    id TEXT PRIMARY KEY,
    goal_id TEXT,
    title TEXT,
    deadline TEXT,
    status TEXT DEFAULT 'not_started',
    notes TEXT,
    FOREIGN KEY (goal_id) REFERENCES goals(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    milestone_id TEXT,
    title TEXT,
    due_date TEXT,
    scheduled_at DATETIME,
    status TEXT DEFAULT 'pending',
    recurrence TEXT,
    reminder_minutes INTEGER DEFAULT 60,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

CREATE TABLE IF NOT EXISTS weekly_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT,
    week_end TEXT,
    focus TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS commitments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    deadline TEXT,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME
);

CREATE TABLE IF NOT EXISTS personal_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    notes TEXT,
    due_date TEXT,
    due_time TEXT,
    due_datetime DATETIME,
    recurrence TEXT,
    recurrence_days TEXT,
    status TEXT DEFAULT 'pending',
    reminder_minutes INTEGER DEFAULT 30,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    next_due DATETIME,
    google_task_id TEXT
);

CREATE TABLE IF NOT EXISTS task_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    reminded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks_sync (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_pull DATETIME,
    last_push DATETIME,
    tasklist_id TEXT,
    pull_count INTEGER DEFAULT 0,
    push_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS deploy_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    commit_hash TEXT,
    commit_message TEXT,
    deployed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    verify_passed INTEGER DEFAULT 0,
    stable INTEGER DEFAULT 0,
    rolled_back INTEGER DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS api_rate_limits (
    api_name TEXT PRIMARY KEY,
    calls_today INTEGER DEFAULT 0,
    calls_this_minute INTEGER DEFAULT 0,
    last_call_at TEXT,
    last_429_at TEXT,
    retry_after_seconds INTEGER DEFAULT 0,
    total_calls_lifetime INTEGER DEFAULT 0,
    quota_used_today INTEGER DEFAULT 0,
    day_reset_at TEXT
);

CREATE TABLE IF NOT EXISTS api_call_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_name TEXT NOT NULL,
    called_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
    cost_units INTEGER DEFAULT 1,
    success INTEGER DEFAULT 1,
    response_code INTEGER,
    was_cached INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_api_call_log_name_time ON api_call_log(api_name, called_at DESC);

CREATE TABLE IF NOT EXISTS poll_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_key TEXT NOT NULL,
    polled_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
    success INTEGER DEFAULT 1,
    duration_ms INTEGER,
    from_cache INTEGER DEFAULT 0,
    error_msg TEXT
);

CREATE INDEX IF NOT EXISTS idx_poll_log_key_time ON poll_log(poll_key, polled_at DESC);
"""

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


def init_db() -> None:
    global _conn
    _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row

    # Enable WAL mode for concurrent access
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA synchronous=NORMAL")
    _conn.commit()

    _conn.executescript(SCHEMA)
    _conn.commit()
    _run_migrations()


def _run_migrations() -> None:
    """Apply incremental schema migrations for existing tables."""
    try:
        cols = {row[1] for row in _conn.execute("PRAGMA table_info(personal_tasks)").fetchall()}
        if cols and "google_task_id" not in cols:
            _conn.execute("ALTER TABLE personal_tasks ADD COLUMN google_task_id TEXT")
            _conn.commit()
    except Exception:
        pass


def _exec(sql: str, params=(), commit: bool = False) -> sqlite3.Cursor:
    with _lock:
        cur = _conn.execute(sql, params)
        if commit:
            _conn.commit()
        return cur
