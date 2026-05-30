"""Google Tasks sync orchestration — event-driven push, heartbeat pull."""

from datetime import datetime, timedelta

from tools.api.google_tasks_api import (
    get_default_tasklist_id,
    pull_tasks,
    push_task,
    complete_task,
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

    completed = get_tasks_completed_since(since)
    pushed = 0
    for task in completed:
        success = complete_task(tasklist_id, task["google_task_id"])
        if success:
            pushed += 1
    return pushed


def pull_from_google() -> int:
    """Pull Google Tasks into local personal_tasks DB. Returns count of new tasks."""
    tasklist_id = get_or_cache_tasklist_id()
    if not tasklist_id:
        return 0

    raw = pull_tasks(tasklist_id)
    google_tasks = raw.get("tasks", [])
    local_tasks = get_personal_tasks("all")
    local_google_ids = {
        t["google_task_id"]
        for t in local_tasks
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
    """Full sync cycle: push new, push completions, pull from Google."""
    try:
        pushed_new = push_new_tasks()
        pushed_done = push_completions()
        pulled = pull_from_google()

        update_sync_record(last_push=datetime.now().isoformat())

        return {
            "status": "ok",
            "pushed_new": pushed_new,
            "pushed_completions": pushed_done,
            "pulled_new": pulled,
        }
    except Exception as e:
        update_sync_record(error=True)
        return {"status": "error", "error": str(e)}
