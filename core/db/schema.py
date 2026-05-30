"""DB schema, connection, and shared primitives."""

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
"""

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


def init_db() -> None:
    global _conn
    _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.executescript(SCHEMA)
    _conn.commit()


def _exec(sql: str, params=(), commit: bool = False) -> sqlite3.Cursor:
    with _lock:
        cur = _conn.execute(sql, params)
        if commit:
            _conn.commit()
        return cur
