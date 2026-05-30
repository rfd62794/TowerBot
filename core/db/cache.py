"""KV cache and tool result cache."""

import json
import datetime

from core.db.schema import _exec


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


def cache_tool_result(tool_name: str, params_hash: str, result: dict, ttl_hours: float) -> None:
    """Cache a tool result with TTL."""
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
