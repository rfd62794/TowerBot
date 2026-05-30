"""Layer 5 — Database.

The only module that touches SQLite. All other layers import from here.
Pure database: no agent, Telegram, or OpenRouter logic.
"""

import os
import json
import sqlite3
import threading
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "privy.db")

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
"""

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


# ── Connection ──
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


# ── Threads ──
def create_thread(thread_id: str) -> None:
    _exec("INSERT INTO threads (id) VALUES (?)", (thread_id,), commit=True)


def update_thread_name(thread_id: str, name: str) -> None:
    _exec("UPDATE threads SET name = ? WHERE id = ?", (name, thread_id), commit=True)


def update_thread_active(thread_id: str) -> None:
    _exec(
        "UPDATE threads SET last_active = CURRENT_TIMESTAMP WHERE id = ?",
        (thread_id,), commit=True,
    )


def list_threads(limit: int = 10) -> list[dict]:
    rows = _exec(
        "SELECT id, name, created, last_active FROM threads "
        "ORDER BY last_active DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Messages ──
def add_message(thread_id: str, role: str, content: str) -> None:
    _exec(
        "INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)",
        (thread_id, role, content), commit=True,
    )


def get_context(thread_id: str, n: int = 10) -> list[dict]:
    rows = _exec(
        "SELECT role, content FROM messages WHERE thread_id = ? "
        "ORDER BY id DESC LIMIT ?",
        (thread_id, n),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


# ── Memory ──
def save_memory(key: str, content: str, layer: str) -> None:
    _exec(
        "INSERT OR REPLACE INTO memory (key, content, layer, updated, active) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP, 1)",
        (key, content, layer), commit=True,
    )


def update_memory(key: str, content: str) -> None:
    _exec(
        "UPDATE memory SET content = ?, updated = CURRENT_TIMESTAMP WHERE key = ?",
        (content, key), commit=True,
    )


def retire_memory(key: str) -> None:
    _exec("UPDATE memory SET active = 0 WHERE key = ?", (key,), commit=True)


def get_memories(query: str, limit: int = 5) -> list[dict]:
    like = f"%{query}%"
    rows = _exec(
        "SELECT key, content, layer FROM memory WHERE active = 1 "
        "AND (key LIKE ? OR content LIKE ?) ORDER BY updated DESC LIMIT ?",
        (like, like, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def list_memories(layer: str | None = None) -> list[dict]:
    if layer:
        rows = _exec(
            "SELECT key, content, layer FROM memory WHERE active = 1 AND layer = ? "
            "ORDER BY layer, key",
            (layer,),
        ).fetchall()
    else:
        rows = _exec(
            "SELECT key, content, layer FROM memory WHERE active = 1 "
            "ORDER BY layer, key"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Model status / throttle tracking ──
def record_throttle(model_id: str, retry_after: float) -> None:
    _exec(
        "INSERT INTO model_status "
        "(model_id, last_429, retry_after_seconds, fail_count, last_checked) "
        "VALUES (?, CURRENT_TIMESTAMP, ?, 1, CURRENT_TIMESTAMP) "
        "ON CONFLICT(model_id) DO UPDATE SET "
        "last_429 = CURRENT_TIMESTAMP, "
        "retry_after_seconds = excluded.retry_after_seconds, "
        "fail_count = model_status.fail_count + 1, "
        "last_checked = CURRENT_TIMESTAMP",
        (model_id, retry_after), commit=True,
    )


def record_success(model_id: str) -> None:
    _exec(
        "INSERT INTO model_status "
        "(model_id, last_success, fail_count, last_429, last_checked) "
        "VALUES (?, CURRENT_TIMESTAMP, 0, NULL, CURRENT_TIMESTAMP) "
        "ON CONFLICT(model_id) DO UPDATE SET "
        "last_success = CURRENT_TIMESTAMP, "
        "fail_count = 0, last_429 = NULL, last_checked = CURRENT_TIMESTAMP",
        (model_id,), commit=True,
    )


def get_throttled_models() -> list[str]:
    rows = _exec(
        "SELECT model_id FROM model_status WHERE last_429 IS NOT NULL "
        "AND datetime(last_429, '+' || retry_after_seconds || ' seconds') "
        "> datetime('now')"
    ).fetchall()
    return [r["model_id"] for r in rows]


def get_model_status_all() -> list[dict]:
    rows = _exec(
        "SELECT model_id, last_429, retry_after_seconds, fail_count, last_success "
        "FROM model_status ORDER BY model_id"
    ).fetchall()
    return [dict(r) for r in rows]


# ── KV cache ──
def cache_model_list(models: list) -> None:
    _exec(
        "INSERT OR REPLACE INTO kv_cache (key, value, updated) "
        "VALUES ('free_tool_models', ?, CURRENT_TIMESTAMP)",
        (json.dumps(models),), commit=True,
    )


def get_cached_model_list() -> list | None:
    row = _exec(
        "SELECT value FROM kv_cache WHERE key = 'free_tool_models' "
        "AND datetime(updated, '+24 hours') > datetime('now')"
    ).fetchone()
    return json.loads(row["value"]) if row else None


# ── Tool cache ──
def cache_tool_result(tool_name: str, params_hash: str, result: dict, ttl_hours: float) -> None:
    """Cache a tool result with TTL."""
    import datetime
    expires_at = (datetime.datetime.now() + datetime.timedelta(hours=ttl_hours)).isoformat()
    _exec(
        "INSERT OR REPLACE INTO tool_cache (tool_name, params_hash, result, expires_at) "
        "VALUES (?, ?, ?, ?)",
        (tool_name, params_hash, json.dumps(result), expires_at), commit=True,
    )


def get_cached_tool_result(tool_name: str, params_hash: str) -> dict | None:
    """Get cached tool result if not expired."""
    row = _exec(
        "SELECT result FROM tool_cache WHERE tool_name = ? AND params_hash = ? "
        "AND expires_at > datetime('now')",
        (tool_name, params_hash),
    ).fetchone()
    return json.loads(row["result"]) if row else None


# ── Channel history ──
def record_channel_day(date: str, views: int, watch_time: float, subs: int) -> None:
    """Record daily channel metrics."""
    _exec(
        "INSERT OR REPLACE INTO channel_history (date, views, watch_time_minutes, subscribers_gained) "
        "VALUES (?, ?, ?, ?)",
        (date, views, watch_time, subs), commit=True,
    )


def get_channel_history(days: int = 30) -> list[dict]:
    """Get channel history for last N days."""
    rows = _exec(
        "SELECT date, views, watch_time_minutes, subscribers_gained, recorded_at "
        "FROM channel_history "
        "WHERE date >= date('now', '-' || ? || ' days') "
        "ORDER BY date ASC",
        (days,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Video history ──
def record_video_day(video_id: str, date: str, views: int, watch_time: float,
                     avg_duration: float, avg_pct: float) -> None:
    _exec(
        "INSERT OR REPLACE INTO video_history "
        "(video_id, date, views, watch_time_minutes, avg_view_duration_seconds, avg_view_percentage) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (video_id, date, views, watch_time, avg_duration, avg_pct), commit=True,
    )


def get_video_history(video_id: str, days: int = 30) -> list[dict]:
    rows = _exec(
        "SELECT * FROM video_history WHERE video_id = ? "
        "AND date >= date('now', '-' || ? || ' days') ORDER BY date DESC",
        (video_id, days),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Game history ──
def record_game_day(appid: int, date: str, players_2weeks: int,
                    owners_low: int, owners_high: int, price_usd: float, on_sale: bool) -> None:
    _exec(
        "INSERT OR REPLACE INTO game_history "
        "(appid, date, players_2weeks, owners_low, owners_high, price_usd, on_sale) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (appid, date, players_2weeks, owners_low, owners_high, price_usd, 1 if on_sale else 0), commit=True,
    )


def get_game_history(appid: int, days: int = 90) -> list[dict]:
    rows = _exec(
        "SELECT * FROM game_history WHERE appid = ? "
        "AND date >= date('now', '-' || ? || ' days') ORDER BY date DESC",
        (appid, days),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Weather history ──
def record_weather_day(date: str, temp_f: float, condition: str, wind_mph: float) -> None:
    _exec(
        "INSERT OR REPLACE INTO weather_history (date, temp_f, condition, wind_mph) "
        "VALUES (?, ?, ?, ?)",
        (date, temp_f, condition, wind_mph), commit=True,
    )


def get_weather_history(days: int = 30) -> list[dict]:
    rows = _exec(
        "SELECT * FROM weather_history WHERE date >= date('now', '-' || ? || ' days') "
        "ORDER BY date DESC",
        (days,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Video metadata cache ──
def upsert_video_metadata(video_id: str, title: str, description: str, tags: str,
                          duration_seconds: int, published_at: str, thumbnail_url: str) -> None:
    _exec(
        "INSERT OR REPLACE INTO video_metadata_cache "
        "(video_id, title, description, tags, duration_seconds, published_at, thumbnail_url, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (video_id, title, description, tags, duration_seconds, published_at, thumbnail_url), commit=True,
    )


def get_video_metadata(video_id: str) -> dict | None:
    row = _exec(
        "SELECT * FROM video_metadata_cache WHERE video_id = ?",
        (video_id,),
    ).fetchone()
    return dict(row) if row else None


def get_all_video_metadata() -> list[dict]:
    rows = _exec("SELECT * FROM video_metadata_cache ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


# ── Scheduled videos ──
def upsert_scheduled_video(video_id: str, title: str, scheduled_time: str, privacy_status: str) -> None:
    _exec(
        "INSERT OR REPLACE INTO scheduled_videos "
        "(video_id, title, scheduled_time, privacy_status, last_checked) "
        "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (video_id, title, scheduled_time, privacy_status), commit=True,
    )


def get_scheduled_videos() -> list[dict]:
    rows = _exec(
        "SELECT * FROM scheduled_videos WHERE scheduled_time >= datetime('now') "
        "ORDER BY scheduled_time ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def clear_old_scheduled() -> None:
    _exec(
        "DELETE FROM scheduled_videos WHERE scheduled_time < datetime('now', '-7 days')",
        commit=True,
    )


# ── Task queue ──
def queue_observation(task_name: str, message: str, priority: str = "normal", scheduled_for: str = None) -> None:
    """Queue an observation for later sending."""
    if scheduled_for is None:
        scheduled_for = "datetime('now')"
    _exec(
        "INSERT INTO task_queue (task_name, message, priority, scheduled_for) "
        "VALUES (?, ?, ?, " + scheduled_for + ")",
        (task_name, message, priority), commit=True,
    )


def get_pending_observations() -> list[dict]:
    """Get unsent observations whose scheduled time has arrived."""
    rows = _exec(
        "SELECT * FROM task_queue WHERE sent = 0 AND scheduled_for <= datetime('now') "
        "ORDER BY priority DESC, created_at ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def mark_sent(observation_id: int) -> None:
    """Mark an observation as sent."""
    _exec(
        "UPDATE task_queue SET sent = 1 WHERE id = ?",
        (observation_id,), commit=True,
    )


def flush_morning_queue() -> list[dict]:
    """Get all unsent queued observations and mark them sent."""
    rows = _exec(
        "SELECT * FROM task_queue WHERE sent = 0 ORDER BY priority DESC, created_at ASC"
    ).fetchall()
    observations = [dict(r) for r in rows]
    
    # Mark all as sent
    if observations:
        _exec(
            "UPDATE task_queue SET sent = 1 WHERE sent = 0",
            commit=True,
        )
    
    return observations


# ── Goals ──
def upsert_goal(goal_id: str, title: str, description: str, deadline: str, 
               status: str = "active", progress_pct: int = 0, notes: str = None) -> None:
    _exec(
        "INSERT OR REPLACE INTO goals (id, title, description, deadline, status, progress_pct, notes, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (goal_id, title, description, deadline, status, progress_pct, notes), commit=True,
    )


def get_goals(status: str = None) -> list[dict]:
    if status:
        rows = _exec(
            "SELECT * FROM goals WHERE status = ? ORDER BY deadline ASC",
            (status,),
        ).fetchall()
    else:
        rows = _exec("SELECT * FROM goals ORDER BY deadline ASC").fetchall()
    return [dict(r) for r in rows]


def get_goal(goal_id: str) -> dict | None:
    row = _exec("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    return dict(row) if row else None


# ── Milestones ──
def upsert_milestone(milestone_id: str, goal_id: str, title: str, deadline: str,
                     status: str = "not_started", notes: str = None) -> None:
    _exec(
        "INSERT OR REPLACE INTO milestones (id, goal_id, title, deadline, status, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (milestone_id, goal_id, title, deadline, status, notes), commit=True,
    )


def get_milestones(goal_id: str = None) -> list[dict]:
    if goal_id:
        rows = _exec(
            "SELECT * FROM milestones WHERE goal_id = ? ORDER BY deadline ASC",
            (goal_id,),
        ).fetchall()
    else:
        rows = _exec("SELECT * FROM milestones ORDER BY deadline ASC").fetchall()
    return [dict(r) for r in rows]


def get_milestone(milestone_id: str) -> dict | None:
    row = _exec("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
    return dict(row) if row else None


# ── Tasks ──
def upsert_task(task_id: str, title: str, due_date: str, milestone_id: str = None,
                scheduled_at: str = None, status: str = "pending", recurrence: str = None,
                reminder_minutes: int = 60) -> None:
    _exec(
        "INSERT OR REPLACE INTO tasks (id, milestone_id, title, due_date, scheduled_at, status, recurrence, reminder_minutes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, milestone_id, title, due_date, scheduled_at, status, recurrence, reminder_minutes), commit=True,
    )


def get_tasks(status: str = None, due_date: str = None) -> list[dict]:
    if status and due_date:
        rows = _exec(
            "SELECT * FROM tasks WHERE status = ? AND due_date = ? ORDER BY due_date ASC",
            (status, due_date),
        ).fetchall()
    elif status:
        rows = _exec(
            "SELECT * FROM tasks WHERE status = ? ORDER BY due_date ASC",
            (status,),
        ).fetchall()
    elif due_date:
        rows = _exec(
            "SELECT * FROM tasks WHERE due_date = ? ORDER BY due_date ASC",
            (due_date,),
        ).fetchall()
    else:
        rows = _exec("SELECT * FROM tasks ORDER BY due_date ASC").fetchall()
    return [dict(r) for r in rows]


def get_task(task_id: str) -> dict | None:
    row = _exec("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def update_task_status(task_id: str, status: str) -> None:
    completed_at = "CURRENT_TIMESTAMP" if status == "complete" else "NULL"
    _exec(
        f"UPDATE tasks SET status = ?, completed_at = {completed_at} WHERE id = ?",
        (status, task_id), commit=True,
    )


def get_tasks_due_today() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    rows = _exec(
        "SELECT * FROM tasks WHERE due_date = ? AND status != 'complete' ORDER BY scheduled_at ASC",
        (today,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_upcoming_scheduled(hours: int = 24) -> list[dict]:
    rows = _exec(
        "SELECT * FROM tasks WHERE scheduled_at IS NOT NULL "
        "AND scheduled_at BETWEEN datetime('now') AND datetime('now', '+' || ? || ' hours') "
        "AND status != 'complete' ORDER BY scheduled_at ASC",
        (hours,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Weekly plans ──
def upsert_weekly_plan(week_start: str, week_end: str, focus: str, notes: str = None) -> None:
    _exec(
        "INSERT OR REPLACE INTO weekly_plans (week_start, week_end, focus, notes) "
        "VALUES (?, ?, ?, ?)",
        (week_start, week_end, focus, notes), commit=True,
    )


def get_current_weekly_plan() -> dict | None:
    today = datetime.now().strftime("%Y-%m-%d")
    row = _exec(
        "SELECT * FROM weekly_plans WHERE ? BETWEEN week_start AND week_end ORDER BY created_at DESC LIMIT 1",
        (today,),
    ).fetchone()
    return dict(row) if row else None
