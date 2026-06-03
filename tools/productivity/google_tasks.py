"""Google Tasks API tools for Agent — full CRUD with duplicate prevention and date normalization."""

from datetime import datetime, timedelta
from api.google.tasks_api import (
    get_default_tasklist_id,
    pull_tasks,
    push_task,
    complete_task,
    delete_task,
    update_task,
)


def _normalize_due_date(due_date: str = None) -> str | None:
    """Normalize due date: if in past, set to today. Returns YYYY-MM-DD or None."""
    if not due_date:
        return None
    
    try:
        due = datetime.fromisoformat(due_date[:10])
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if due < today:
            # Past date - normalize to today
            return today.strftime("%Y-%m-%d")
        return due.strftime("%Y-%m-%d")
    except Exception:
        # Invalid date format, return None
        return None


def _check_duplicate(title: str, due_date: str = None) -> dict | None:
    """Check if a task with same title and due date already exists in Google Tasks."""
    tasklist_id = get_default_tasklist_id()
    if not tasklist_id:
        return None
    
    raw = tasklist_id.get("tasklist_id")
    if not raw:
        return None
    
    tasks = pull_tasks(raw).get("tasks", [])
    normalized_due = _normalize_due_date(due_date)
    
    for task in tasks:
        if task.get("title") == title and task.get("status") != "completed":
            task_due = task.get("due", "")[:10] if task.get("due") else None
            if task_due == normalized_due or (not task_due and not normalized_due):
                return task
    
    return None


def list_google_tasks(show_completed: bool = False) -> dict:
    """
    List all tasks from Google Tasks.
    
    PARAMS:
      show_completed (bool): Include completed tasks (default: False)
    
    RETURNS: dict with ok, tasks (list), count
    """
    tasklist_id = get_default_tasklist_id()
    if not tasklist_id or not tasklist_id.get("tasklist_id"):
        return {"ok": False, "error": "Could not get tasklist ID"}
    
    raw = pull_tasks(tasklist_id["tasklist_id"], show_completed=show_completed)
    tasks = raw.get("tasks", [])
    
    # Filter out deleted tasks (Google marks deleted tasks with deleted=true instead of removing them)
    tasks = [t for t in tasks if not t.get("deleted")]
    
    # Normalize dates for display
    for task in tasks:
        if task.get("due"):
            task["due_date"] = task["due"][:10]
        else:
            task["due_date"] = None
    
    return {
        "ok": True,
        "tasks": tasks,
        "count": len(tasks)
    }


def get_google_task(task_id: str) -> dict:
    """
    Get a specific Google Task by ID.
    
    PARAMS:
      task_id (str): Google Task ID
    
    RETURNS: dict with ok, task (dict) or error
    """
    tasklist_id = get_default_tasklist_id()
    if not tasklist_id or not tasklist_id.get("tasklist_id"):
        return {"ok": False, "error": "Could not get tasklist ID"}
    
    raw = pull_tasks(tasklist_id["tasklist_id"])
    tasks = raw.get("tasks", [])
    
    # Filter out deleted tasks (Google marks deleted tasks with deleted=true instead of removing them)
    tasks = [t for t in tasks if not t.get("deleted")]
    
    for task in tasks:
        if task.get("id") == task_id:
            if task.get("due"):
                task["due_date"] = task["due"][:10]
            else:
                task["due_date"] = None
            return {"ok": True, "task": task}
    
    return {"ok": False, "error": f"Task not found: {task_id}"}


def create_google_task(title: str, notes: str = None, due_date: str = None, check_duplicate: bool = True) -> dict:
    """
    Create a new task in Google Tasks with duplicate prevention and date normalization.
    
    PARAMS:
      title (str): Task title (required)
      notes (str): Optional notes/description
      due_date (str): Due date in YYYY-MM-DD format (optional)
      check_duplicate (bool): Check for existing duplicates (default: True)
    
    RETURNS: dict with ok, task (dict) or error
    """
    if not title:
        return {"ok": False, "error": "Title is required"}
    
    # Normalize due date (push past dates to today)
    normalized_due = _normalize_due_date(due_date)
    
    # Check for duplicates if enabled
    if check_duplicate:
        duplicate = _check_duplicate(title, normalized_due)
        if duplicate:
            return {
                "ok": False,
                "error": "Duplicate task exists",
                "duplicate": duplicate,
                "message": f"A task with title '{title}' and due date '{normalized_due or 'no date'}' already exists"
            }
    
    tasklist_id = get_default_tasklist_id()
    if not tasklist_id or not tasklist_id.get("tasklist_id"):
        return {"ok": False, "error": "Could not get tasklist ID"}
    
    result = push_task(
        tasklist_id["tasklist_id"],
        title=title,
        notes=notes,
        due=normalized_due,
    )
    
    if result:
        if result.get("due"):
            result["due_date"] = result["due"][:10]
        else:
            result["due_date"] = None
        return {"ok": True, "task": result}
    
    return {"ok": False, "error": "Failed to create task"}


def update_google_task(task_id: str, title: str = None, notes: str = None, due_date: str = None, status: str = None) -> dict:
    """
    Update an existing Google Task with date normalization.
    
    PARAMS:
      task_id (str): Google Task ID (required)
      title (str): New title (optional)
      notes (str): New notes (optional)
      due_date (str): New due date in YYYY-MM-DD format (optional)
      status (str): New status: 'needsAction' or 'completed' (optional)
    
    RETURNS: dict with ok, task (dict) or error
    """
    if not task_id:
        return {"ok": False, "error": "Task ID is required"}
    
    # Normalize due date (push past dates to today)
    normalized_due = _normalize_due_date(due_date)
    
    tasklist_id = get_default_tasklist_id()
    if not tasklist_id or not tasklist_id.get("tasklist_id"):
        return {"ok": False, "error": "Could not get tasklist ID"}
    
    result = update_task(
        tasklist_id["tasklist_id"],
        task_id,
        title=title,
        notes=notes,
        due=normalized_due,
        status=status,
    )
    
    if result:
        if result.get("due"):
            result["due_date"] = result["due"][:10]
        else:
            result["due_date"] = None
        return {"ok": True, "task": result}
    
    return {"ok": False, "error": "Failed to update task"}


def complete_google_task(task_id: str) -> dict:
    """
    Mark a Google Task as completed.
    
    PARAMS:
      task_id (str): Google Task ID (required)
    
    RETURNS: dict with ok, message or error
    """
    if not task_id:
        return {"ok": False, "error": "Task ID is required"}
    
    tasklist_id = get_default_tasklist_id()
    if not tasklist_id or not tasklist_id.get("tasklist_id"):
        return {"ok": False, "error": "Could not get tasklist ID"}
    
    success = complete_task(tasklist_id["tasklist_id"], task_id)
    
    if success:
        return {"ok": True, "message": f"Task {task_id} marked as completed"}
    
    return {"ok": False, "error": "Failed to complete task"}


def delete_google_task(task_id: str) -> dict:
    """
    Delete a Google Task.
    
    PARAMS:
      task_id (str): Google Task ID (required)
    
    RETURNS: dict with ok, message or error
    """
    if not task_id:
        return {"ok": False, "error": "Task ID is required"}
    
    tasklist_id = get_default_tasklist_id()
    if not tasklist_id or not tasklist_id.get("tasklist_id"):
        return {"ok": False, "error": "Could not get tasklist ID"}
    
    success = delete_task(tasklist_id["tasklist_id"], task_id)
    
    if success:
        return {"ok": True, "message": f"Task {task_id} deleted"}
    
    return {"ok": False, "error": "Failed to delete task"}


def sync_google_tasks() -> dict:
    """
    Trigger full sync between local DB and Google Tasks.
    This calls the existing sync orchestration.
    
    RETURNS: dict with sync status and counts
    """
    from tools.productivity.sync import run_sync
    return run_sync()
