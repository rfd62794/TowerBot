"""Admin tools for database maintenance and cleanup."""

from infra.db.schema import _exec


def purge_null_tasks() -> dict:
    """Admin: cancel all queued tasks with null or empty prompts."""
    cur = _exec(
        "UPDATE task_queue SET status='cancelled' "
        "WHERE (prompt IS NULL OR prompt='') AND status='queued'",
        commit=True
    )
    return {"cancelled": cur.rowcount, "status": "success"}
