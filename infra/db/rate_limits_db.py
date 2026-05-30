"""core/db/rate_limits_db.py

Rate limit database operations.
All API rate limit state and call logging.
"""

from infra.db.schema import _exec
from datetime import datetime


def get_api_state(api_name: str) -> dict:
    """Get current state row for an API.
    Returns defaults if never seen before."""
    row = _exec("""
        SELECT api_name, calls_today,
               calls_this_minute, last_call_at,
               last_429_at, retry_after_seconds,
               total_calls_lifetime,
               quota_used_today, day_reset_at
        FROM api_rate_limits
        WHERE api_name = ?
    """, [api_name]).fetchone()
    
    if row is None:
        return {
            "api_name": api_name,
            "calls_today": 0,
            "calls_this_minute": 0,
            "last_call_at": None,
            "last_429_at": None,
            "retry_after_seconds": 0,
            "total_calls_lifetime": 0,
            "quota_used_today": 0,
            "day_reset_at": None
        }
    return dict(zip([
        "api_name", "calls_today",
        "calls_this_minute", "last_call_at",
        "last_429_at", "retry_after_seconds",
        "total_calls_lifetime",
        "quota_used_today", "day_reset_at"
    ], row))


def upsert_api_state(api_name: str, **fields) -> None:
    """Update or insert API state."""
    existing = get_api_state(api_name)
    existing.update(fields)
    existing["api_name"] = api_name
    
    _exec("""
        INSERT OR REPLACE INTO api_rate_limits
          (api_name, calls_today,
           calls_this_minute, last_call_at,
           last_429_at, retry_after_seconds,
           total_calls_lifetime,
           quota_used_today, day_reset_at)
        VALUES
          (?,?,?,?,?,?,?,?,?)
    """, [
        existing["api_name"],
        existing["calls_today"],
        existing["calls_this_minute"],
        existing["last_call_at"],
        existing["last_429_at"],
        existing["retry_after_seconds"],
        existing["total_calls_lifetime"],
        existing["quota_used_today"],
        existing["day_reset_at"]
    ], commit=True)


def log_api_call(api_name: str,
                 cost_units: int = 1,
                 success: bool = True,
                 response_code: int = 200,
                 was_cached: bool = False
                 ) -> None:
    _exec("""
        INSERT INTO api_call_log
          (api_name, cost_units, success,
           response_code, was_cached)
        VALUES (?, ?, ?, ?, ?)
    """, [
        api_name, cost_units,
        1 if success else 0,
        response_code,
        1 if was_cached else 0
    ], commit=True)


def get_call_log(api_name: str = None,
                 limit: int = 100
                 ) -> list[dict]:
    if api_name:
        rows = _exec("""
            SELECT api_name, called_at,
                   cost_units, success,
                   response_code, was_cached
            FROM api_call_log
            WHERE api_name = ?
            ORDER BY called_at DESC
            LIMIT ?
        """, [api_name, limit]).fetchall()
    else:
        rows = _exec("""
            SELECT api_name, called_at,
                   cost_units, success,
                   response_code, was_cached
            FROM api_call_log
            ORDER BY called_at DESC
            LIMIT ?
        """, [limit]).fetchall()
    
    return [dict(zip([
        "api_name", "called_at", "cost_units",
        "success", "response_code", "was_cached"
    ], r)) for r in rows]


def get_all_api_states() -> list[dict]:
    rows = _exec("""
        SELECT * FROM api_rate_limits
        ORDER BY api_name ASC
    """).fetchall()
    return [dict(zip([
        "api_name", "calls_today",
        "calls_this_minute", "last_call_at",
        "last_429_at", "retry_after_seconds",
        "total_calls_lifetime",
        "quota_used_today", "day_reset_at"
    ], r)) for r in rows]
