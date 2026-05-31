"""KV cache and tool result cache."""

import json
import datetime

from infra.db.manager import db


def cache_model_list(models: list) -> None:
    db.exec(
        "INSERT OR REPLACE INTO kv_cache (key, value, updated) "
        "VALUES ('free_tool_models', ?, CURRENT_TIMESTAMP)",
        (json.dumps(models),), commit=True,
    )


def get_cached_model_list() -> list | None:
    row = db.exec(
        "SELECT value FROM kv_cache WHERE key = 'free_tool_models' "
        "AND datetime(updated, '+24 hours') > datetime('now')"
    ).fetchone()
    return json.loads(row["value"]) if row else None


def cache_tool_result(tool_name: str, params_hash: str, result: dict, ttl_hours: float) -> None:
    """Cache a tool result with TTL."""
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(hours=ttl_hours)).strftime("%Y-%m-%d %H:%M:%S")
    fetched_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    db.exec(
        "INSERT OR REPLACE INTO tool_cache (tool_name, params_hash, result, expires_at, fetched_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (tool_name, params_hash, json.dumps(result), expires_at, fetched_at), commit=True,
    )


def get_cached_tool_result(tool_name: str, params_hash: str) -> dict | None:
    """Get cached tool result if not expired."""
    row = db.exec(
        "SELECT result FROM tool_cache WHERE tool_name = ? AND params_hash = ? "
        "AND expires_at > datetime('now')",
        (tool_name, params_hash),
    ).fetchone()
    return json.loads(row["result"]) if row else None


def get_stale_cached_result(tool_name: str, params_hash: str) -> dict | None:
    """
    Returns most recent cached result regardless of TTL expiry.
    Returns None only if no record exists at all.
    Adds metadata to returned dict: _stale, _cached_at, _age_minutes.
    """
    row = db.exec(
        "SELECT result, fetched_at FROM tool_cache "
        "WHERE tool_name = ? AND params_hash = ? "
        "ORDER BY fetched_at DESC LIMIT 1",
        (tool_name, params_hash),
    ).fetchone()
    if row is None:
        return None

    result = json.loads(row["result"])
    fetched_at_str = row["fetched_at"]

    # SQLite CURRENT_TIMESTAMP uses space separator, Python isoformat uses T
    # Normalize to T separator for parsing
    fetched_at = datetime.datetime.fromisoformat(fetched_at_str.replace(" ", "T"))
    now = datetime.datetime.now()
    age_minutes = int((now - fetched_at).total_seconds() / 60)

    result["_stale"] = True
    result["_cached_at"] = fetched_at_str
    result["_age_minutes"] = age_minutes

    return result


def record_preload_result(
    tool_name: str,
    params_hash: str,
    result: dict,
    ttl_hours: float,
    success: bool,
    duration_ms: int,
    error_msg: str = None,
) -> None:
    """
    Writes to tool_cache (same as cache_tool_result) AND writes a row
    to preload_log tracking metadata.
    """
    if success:
        cache_tool_result(tool_name, params_hash, result, ttl_hours)

    db.exec(
        "INSERT INTO preload_log (tool_name, params_hash, fetched_at, success, duration_ms, error_msg) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (tool_name, params_hash, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 1 if success else 0, duration_ms, error_msg),
        commit=True,
    )


def get_preload_status() -> list[dict]:
    """
    Returns last fetch attempt per tool_name from preload_log.
    One row per tool. Includes age in minutes.
    """
    rows = db.exec(
        "SELECT tool_name, fetched_at, success, duration_ms, error_msg "
        "FROM preload_log "
        "WHERE (tool_name, fetched_at) IN (SELECT tool_name, MAX(fetched_at) FROM preload_log GROUP BY tool_name) "
        "ORDER BY tool_name ASC"
    ).fetchall()

    results = []
    for row in rows:
        # Normalize space separator to T for parsing
        last_fetch = datetime.datetime.fromisoformat(row["fetched_at"].replace(" ", "T"))
        age_minutes = int((datetime.datetime.now() - last_fetch).total_seconds() / 60)

        results.append({
            "tool_name": row["tool_name"],
            "last_fetch": row["fetched_at"],
            "age_minutes": age_minutes,
            "success": bool(row["success"]),
            "duration_ms": row["duration_ms"],
            "error_msg": row["error_msg"],
        })

    return results
