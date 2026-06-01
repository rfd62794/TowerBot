"""Admin tools for database maintenance and cleanup."""

from infra.db import get_db
from tools._tool import tool


@tool
def purge_null_tasks() -> dict:
    """Admin: cancel all queued tasks with null or empty prompts."""
    with get_db() as db:
        result = db.execute(
            "UPDATE task_queue SET status='cancelled' "
            "WHERE (prompt IS NULL OR prompt='') AND status='queued'"
        )
        db.commit()
        return {"cancelled": result.rowcount, "status": "success"}
