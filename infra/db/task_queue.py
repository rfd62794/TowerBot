"""Task queue CRUD for delegation system."""

from datetime import datetime
from typing import List, Dict, Optional
from infra.db.schema import _exec


def add_task(
    prompt: str,
    task_name: str = "delegated",
    context: str = None,
    priority: str = "normal",
    source: str = "claude",
    run_at: str = None,
) -> int:
    """
    Insert task into queue. Returns task_id.
    
    Args:
        prompt: Full task instructions
        task_name: Short label for the task
        context: Additional context or constraints
        priority: urgent|high|normal|low
        source: claude|autonomous
        run_at: ISO datetime, None = now
    
    Returns:
        task_id (integer)
    """
    queued_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor = _exec(
        """
        INSERT INTO task_queue (task_name, message, priority, created_at, scheduled_for, source, prompt, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (task_name, context or "", priority, queued_at, run_at, source, prompt, "queued"),
        commit=True
    )
    return cursor.lastrowid


def get_due_tasks(limit: int = 5) -> List[Dict]:
    """
    Returns queued tasks where run_at <= now(),
    ordered by priority (urgent first) then queued_at.
    Only returns tasks with status='queued'.
    
    Args:
        limit: Maximum number of tasks to return
    
    Returns:
        List of task dicts
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    rows = _exec(
        """
        SELECT id, task_name, message, priority, created_at, scheduled_for, source, prompt, status
        FROM task_queue
        WHERE status = 'queued'
        AND (scheduled_for IS NULL OR scheduled_for <= ?)
        ORDER BY
            CASE priority
                WHEN 'urgent' THEN 1
                WHEN 'high' THEN 2
                WHEN 'normal' THEN 3
                WHEN 'low' THEN 4
            END,
            created_at ASC
        LIMIT ?
        """,
        (now, limit)
    ).fetchall()
    
    return [dict(row) for row in rows]


def mark_running(task_id: int) -> None:
    """Set status=running, started_at=now()"""
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _exec(
        "UPDATE task_queue SET status = 'running', started_at = ? WHERE id = ?",
        (started_at, task_id),
        commit=True
    )


def mark_complete(task_id: int, result: str, duration_ms: int) -> None:
    """Set status=complete, result, completed_at, duration_ms"""
    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _exec(
        "UPDATE task_queue SET status = 'complete', result = ?, completed_at = ?, duration_ms = ? WHERE id = ?",
        (result, completed_at, duration_ms, task_id),
        commit=True
    )


def mark_failed(task_id: int, error: str) -> None:
    """Set status=failed, result=error message"""
    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _exec(
        "UPDATE task_queue SET status = 'failed', result = ?, completed_at = ? WHERE id = ?",
        (error, completed_at, task_id),
        commit=True
    )


def cancel_task(task_id: int) -> bool:
    """
    Set status=cancelled if task is still queued.
    Returns False if already running/complete.
    
    Args:
        task_id: Task ID to cancel
    
    Returns:
        True if cancelled, False otherwise
    """
    task = get_task_status(task_id)
    if not task:
        return False
    if task["status"] not in ["queued"]:
        return False
    
    _exec(
        "UPDATE task_queue SET status = 'cancelled' WHERE id = ?",
        (task_id,),
        commit=True
    )
    return True


def get_task_status(task_id: int) -> Optional[Dict]:
    """
    Returns full task row as dict.
    None if task_id not found.
    
    Args:
        task_id: Task ID to query
    
    Returns:
        Task dict or None
    """
    row = _exec(
        "SELECT * FROM task_queue WHERE id = ?",
        (task_id,)
    ).fetchone()
    
    if row:
        return dict(row)
    return None


def list_pending() -> List[Dict]:
    """
    Returns all queued + running tasks, newest first.
    
    Returns:
        List of task dicts
    """
    rows = _exec(
        """
        SELECT id, task_name, message, priority, created_at, scheduled_for, source, prompt, status
        FROM task_queue
        WHERE status IN ('queued', 'running')
        ORDER BY created_at DESC
        """
    ).fetchall()
    
    return [dict(row) for row in rows]
