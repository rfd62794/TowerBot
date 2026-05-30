"""Polling log database operations."""

from core.db.schema import _exec


def record_poll(poll_key: str,
                success: bool,
                duration_ms: int,
                from_cache: bool = False,
                error_msg: str = None) -> None:
    """Record a poll execution in poll_log."""
    sql = """
    INSERT INTO poll_log (poll_key, success, duration_ms, from_cache, error_msg)
    VALUES (?, ?, ?, ?, ?)
    """
    _exec(sql, (poll_key, 1 if success else 0, duration_ms, 1 if from_cache else 0, error_msg), commit=True)


def get_last_poll(poll_key: str) -> dict | None:
    """Get the most recent poll log entry for a key. Returns None if never polled."""
    sql = """
    SELECT poll_key, polled_at, success, duration_ms, from_cache, error_msg
    FROM poll_log
    WHERE poll_key = ?
    ORDER BY polled_at DESC
    LIMIT 1
    """
    row = _exec(sql, (poll_key,)).fetchone()
    if row is None:
        return None
    return dict(row)


def get_all_last_polls() -> list[dict]:
    """Get the most recent poll log entry for each poll_key."""
    sql = """
    SELECT poll_key, polled_at, success, duration_ms, from_cache, error_msg
    FROM poll_log
    WHERE id IN (
        SELECT MAX(id)
        FROM poll_log
        GROUP BY poll_key
    )
    ORDER BY poll_key
    """
    rows = _exec(sql).fetchall()
    return [dict(row) for row in rows]
