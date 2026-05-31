"""Autonomous task logging — agent_actions table access."""

from datetime import datetime, timedelta
from infra.db.schema import _exec


def record_agent_action(task_name: str, result: str, duration_ms: int, urgent: int = 0):
    """
    Record an autonomous task execution to the database.

    Args:
        task_name: Name of the task (e.g., "email_triage")
        result: Task output or error message
        duration_ms: Execution time in milliseconds
        urgent: 1 if result starts with "URGENT:", 0 otherwise
    """
    ran_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _exec(
        "INSERT INTO agent_actions (task_name, ran_at, result, duration_ms, urgent) VALUES (?, ?, ?, ?, ?)",
        (task_name, ran_at, result, duration_ms, urgent),
        commit=True
    )


def get_overnight_actions():
    """
    Get autonomous actions from the last 8 hours.

    Returns:
        List of dicts with task_name, ran_at, result, duration_ms, urgent
    """
    cutoff = (datetime.now() - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    rows = _exec(
        "SELECT task_name, ran_at, result, duration_ms, urgent FROM agent_actions "
        "WHERE ran_at >= ? ORDER BY ran_at DESC",
        (cutoff,)
    ).fetchall()

    return [
        {
            "task_name": row["task_name"],
            "ran_at": row["ran_at"],
            "result": row["result"],
            "duration_ms": row["duration_ms"],
            "urgent": row["urgent"],
        }
        for row in rows
    ]
