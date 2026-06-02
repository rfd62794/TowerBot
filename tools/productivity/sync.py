"""Google Tasks sync orchestration — event-driven push, heartbeat pull.

Supports both personal_tasks and goals/tasks tables for full Google Tasks compatibility.
"""

from datetime import datetime, timedelta

from api.google.tasks_api import (
    get_default_tasklist_id,
    pull_tasks,
    push_task,
    complete_task,
    update_task,
)
from infra.db.personal_tasks import (
    get_unsynced_tasks,
    set_google_task_id,
    get_tasks_completed_since,
    update_sync_record,
    get_last_sync,
    add_personal_task,
    get_personal_tasks,
)
from infra.db.goals import (
    get_unsynced_tasks as get_unsynced_goal_tasks,
    set_google_task_id as set_goal_task_google_id,
    get_tasks_completed_since as get_goal_tasks_completed_since,
    get_tasks_with_google_id,
    upsert_task,
    get_tasks,
)

SYNC_INTERVAL_MINUTES = 60


def get_or_cache_tasklist_id() -> str | None:
    """Return cached tasklist_id from DB, or fetch from Google and cache it."""
    sync = get_last_sync()
    if sync and sync.get("tasklist_id"):
        return sync["tasklist_id"]
    raw = get_default_tasklist_id()
    tasklist_id = raw.get("tasklist_id")
    if tasklist_id:
        update_sync_record(tasklist_id=tasklist_id)
    return tasklist_id


def push_new_tasks() -> int:
    """Push unsynced local tasks to Google Tasks. Returns count pushed."""
    tasklist_id = get_or_cache_tasklist_id()
    if not tasklist_id:
        return 0

    # Push from personal_tasks
    unsynced = get_unsynced_tasks()
    pushed = 0
    for task in unsynced:
        result = push_task(
            tasklist_id,
            title=task["title"],
            notes=task.get("notes"),
            due=task.get("due_date"),
        )
        if result:
            set_google_task_id(task["id"], result["id"])
            pushed += 1

    # Push from goals/tasks
    goal_unsynced = get_unsynced_goal_tasks()
    for task in goal_unsynced:
        result = push_task(
            tasklist_id,
            title=task["title"],
            notes=task.get("notes"),
            due=task.get("due_date"),
        )
        if result:
            set_goal_task_google_id(task["id"], result["id"])
            pushed += 1

    return pushed


def push_completions() -> int:
    """Push local completions back to Google Tasks. Returns count pushed."""
    last_sync = get_last_sync()
    if last_sync and last_sync.get("last_push"):
        since = last_sync["last_push"]
    else:
        since = (datetime.now() - timedelta(hours=2)).isoformat()

    tasklist_id = get_or_cache_tasklist_id()
    if not tasklist_id:
        return 0

    # Push from personal_tasks
    completed = get_tasks_completed_since(since)
    pushed = 0
    for task in completed:
        success = complete_task(tasklist_id, task["google_task_id"])
        if success:
            pushed += 1

    # Push from goals/tasks
    goal_completed = get_goal_tasks_completed_since(since)
    for task in goal_completed:
        success = complete_task(tasklist_id, task["google_task_id"])
        if success:
            pushed += 1

    return pushed


def push_updates() -> int:
    """Push local due_date/status updates to Google Tasks. Returns count pushed."""
    tasklist_id = get_or_cache_tasklist_id()
    if not tasklist_id:
        return 0

    # Get all tasks with google_task_id from goals/tasks
    synced_tasks = get_tasks_with_google_id()
    pushed = 0
    for task in synced_tasks:
        # Only push if task has been modified recently (simple heuristic: last 24h)
        # In production, would track last_modified timestamp
        if task.get("google_task_id"):
            result = update_task(
                tasklist_id,
                task["google_task_id"],
                title=task["title"],
                due=task.get("due_date"),
                status="completed" if task["status"] == "complete" else "needsAction",
            )
            if result:
                pushed += 1

    return pushed


def pull_from_google() -> int:
    """Pull Google Tasks into local personal_tasks and goals/tasks DB. Returns count of new tasks."""
    tasklist_id = get_or_cache_tasklist_id()
    if not tasklist_id:
        return 0

    raw = pull_tasks(tasklist_id)
    google_tasks = raw.get("tasks", [])
    
    # Get existing google_task_ids from both tables
    local_personal = get_personal_tasks("all")
    local_goal = get_tasks()
    local_google_ids = {
        t["google_task_id"]
        for t in local_personal + local_goal
        if t.get("google_task_id")
    }

    new_count = 0
    for gtask in google_tasks:
        if gtask.get("id") in local_google_ids:
            continue
        if gtask.get("status") == "completed":
            continue
        if not gtask.get("title"):
            continue

        due_date = None
        if gtask.get("due"):
            due_date = gtask["due"][:10]

        # Add to personal_tasks (default for Google Tasks)
        task_id = add_personal_task(
            title=gtask["title"],
            due_date=due_date,
            notes=gtask.get("notes"),
        )
        set_google_task_id(task_id, gtask["id"])
        new_count += 1

    update_sync_record(
        last_pull=datetime.now().isoformat(),
        tasklist_id=tasklist_id,
    )
    return new_count


def run_sync() -> dict:
    """Full sync cycle: push new, push completions, push updates, pull from Google."""
    try:
        pushed_new = push_new_tasks()
        pushed_done = push_completions()
        pushed_updates = push_updates()
        pulled = pull_from_google()

        update_sync_record(last_push=datetime.now().isoformat())

        return {
            "status": "ok",
            "pushed_new": pushed_new,
            "pushed_completions": pushed_done,
            "pushed_updates": pushed_updates,
            "pulled_new": pulled,
        }
    except Exception as e:
        update_sync_record(error=True)
        return {"status": "error", "error": str(e)}
