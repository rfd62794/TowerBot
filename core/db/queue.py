"""Task queue CRUD."""

from core.db.schema import _exec


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

    if observations:
        _exec(
            "UPDATE task_queue SET sent = 1 WHERE sent = 0",
            commit=True,
        )

    return observations
