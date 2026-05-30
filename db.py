"""Layer 5 — Database.

The only module that touches SQLite. All other layers import from here.
Pure database: no agent, Telegram, or OpenRouter logic.
"""

import os
import json
import sqlite3
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "privy.db")

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
