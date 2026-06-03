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


CREATE TABLE IF NOT EXISTS task_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    reminded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Notification deduplication for Google Tasks overdue alerts (ADR-038)
CREATE TABLE IF NOT EXISTS task_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    google_task_id TEXT NOT NULL,
    notification_type TEXT NOT NULL DEFAULT 'overdue',
    last_notified_at TEXT NOT NULL,
    UNIQUE(google_task_id, notification_type)
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

CREATE TABLE IF NOT EXISTS bot_state (
    id INTEGER PRIMARY KEY,
    dev_mode INTEGER DEFAULT 0,
    paused_at TEXT,
    auto_resume_at TEXT
);

CREATE TABLE IF NOT EXISTS chains (
    id TEXT PRIMARY KEY,
    template_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    current_step INTEGER NOT NULL DEFAULT 0,
    payload_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS chain_steps (
    id TEXT PRIMARY KEY,
    chain_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    step_type TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    input_payload_id TEXT,
    output_payload_id TEXT,
    started_at TEXT,
    completed_at TEXT,
    error TEXT,
    FOREIGN KEY (chain_id) REFERENCES chains(id)
);

CREATE TABLE IF NOT EXISTS chain_payloads (
    id TEXT PRIMARY KEY,
    chain_id TEXT NOT NULL,
    step_id TEXT,
    type TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT 'v1',
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (chain_id) REFERENCES chains(id)
);

CREATE TABLE IF NOT EXISTS experimental_tools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_url TEXT,
    input_schema TEXT NOT NULL,
    handler_code TEXT,
    status TEXT NOT NULL DEFAULT 'experimental',
    use_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    promoted_at TEXT,
    last_used_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS pattern_candidates (
    id TEXT PRIMARY KEY,
    step_sequence_hash TEXT NOT NULL UNIQUE,
    observed_count INTEGER NOT NULL DEFAULT 1,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    success_rate REAL NOT NULL DEFAULT 0.0,
    promotion_status TEXT NOT NULL DEFAULT 'candidate',
    template_draft TEXT
);

CREATE TABLE IF NOT EXISTS approval_listeners (
    id TEXT PRIMARY KEY,
    chain_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    telegram_chat_id TEXT NOT NULL,
    message_id TEXT,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting',
    response TEXT,
    FOREIGN KEY (chain_id) REFERENCES chains(id)
);
"""

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


def init_db(db_path: str = DB_PATH) -> None:
    global _conn
    _conn = sqlite3.connect(db_path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row

    # WAL mode only applies to file-based DBs (not :memory:)
    if db_path != ":memory:":
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

    # Migration: add created_at to commitments if missing
    try:
        cols = {row[1] for row in _conn.execute("PRAGMA table_info(commitments)").fetchall()}
        if cols and "created_at" not in cols:
            _conn.execute("ALTER TABLE commitments ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            _conn.commit()
    except Exception:
        pass

    # Migration: add agent_actions table
    try:
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT NOT NULL,
                ran_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
                result TEXT,
                duration_ms INTEGER,
                urgent INTEGER DEFAULT 0
            )
        """)
        _conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_actions_ran
            ON agent_actions(task_name, ran_at DESC)
        """)
        _conn.commit()
    except Exception:
        pass

    # Migration: add post_pipeline table
    try:
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS post_pipeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL UNIQUE,
                stage INTEGER DEFAULT 0,
                q1_prompt TEXT,
                research TEXT,
                skeleton TEXT,
                wp_post_id INTEGER,
                wp_edit_url TEXT,
                created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
                updated_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
            )
        """)
        _conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_post_pipeline_stage
            ON post_pipeline(stage DESC, updated_at DESC)
        """)
        _conn.commit()
    except Exception:
        pass

    # Migration: add model_usage table
    try:
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS model_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                called_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                success INTEGER DEFAULT 1,
                error_code INTEGER,
                latency_ms INTEGER
            )
        """)
        _conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_usage_model_time
            ON model_usage(model_id, called_at DESC)
        """)
        _conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_usage_provider_time
            ON model_usage(provider, called_at DESC)
        """)
        _conn.commit()
    except Exception:
        pass

    # Migration: add system_metrics table
    try:
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
                ram_used_gb REAL,
                ram_free_gb REAL,
                disk_free_gb REAL,
                cpu_percent REAL,
                ollama_model TEXT,
                ollama_ram_gb REAL
            )
        """)
        _conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_system_metrics_recorded_at
            ON system_metrics(recorded_at DESC)
        """)
        _conn.commit()
    except Exception:
        pass

    # Migration: add budget_tracking table
    try:
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS budget_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
                provider TEXT NOT NULL,
                model_id TEXT NOT NULL,
                daily_cap_usd REAL,
                daily_spent_usd REAL DEFAULT 0.0,
                daily_remaining_usd REAL,
                reset_at TEXT
            )
        """)
        _conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_budget_tracking_provider_model
            ON budget_tracking(provider, model_id)
        """)
        _conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_budget_tracking_recorded_at
            ON budget_tracking(recorded_at DESC)
        """)
        _conn.commit()
    except Exception:
        pass

    # Migration: add delegation columns to task_queue
    try:
        cols = {row[1] for row in _conn.execute("PRAGMA table_info(task_queue)").fetchall()}
        if "source" not in cols:
            _conn.execute("ALTER TABLE task_queue ADD COLUMN source TEXT DEFAULT 'autonomous'")
        if "prompt" not in cols:
            _conn.execute("ALTER TABLE task_queue ADD COLUMN prompt TEXT")
        if "status" not in cols:
            _conn.execute("ALTER TABLE task_queue ADD COLUMN status TEXT DEFAULT 'queued'")
        if "result" not in cols:
            _conn.execute("ALTER TABLE task_queue ADD COLUMN result TEXT")
        if "started_at" not in cols:
            _conn.execute("ALTER TABLE task_queue ADD COLUMN started_at TEXT")
        if "completed_at" not in cols:
            _conn.execute("ALTER TABLE task_queue ADD COLUMN completed_at TEXT")
        if "duration_ms" not in cols:
            _conn.execute("ALTER TABLE task_queue ADD COLUMN duration_ms INTEGER")
        _conn.commit()
    except Exception:
        pass

    # Migration: add delegation columns to agent_actions
    try:
        cols = {row[1] for row in _conn.execute("PRAGMA table_info(agent_actions)").fetchall()}
        if "source" not in cols:
            _conn.execute("ALTER TABLE agent_actions ADD COLUMN source TEXT DEFAULT 'autonomous'")
        if "source_task_id" not in cols:
            _conn.execute("ALTER TABLE agent_actions ADD COLUMN source_task_id INTEGER")
        _conn.commit()
    except Exception:
        pass



def _exec(sql: str, params=(), commit: bool = False) -> sqlite3.Cursor:
    with _lock:
        cur = _conn.execute(sql, params)
        if commit:
            _conn.commit()
        return cur
