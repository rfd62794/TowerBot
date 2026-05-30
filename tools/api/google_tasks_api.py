"""Google Tasks API client — raw API calls only."""

from googleapiclient.discovery import build
from tools.api.youtube_api import _get_credentials


DEFAULT_TASKLIST = "@default"


def _get_tasks_client():
    creds = _get_credentials()
    return build("tasks", "v1", credentials=creds, cache_discovery=False)


def get_default_tasklist_id() -> str | None:
    try:
        client = _get_tasks_client()
        result = client.tasklists().list(maxResults=10).execute()
        lists = result.get("items", [])
        if not lists:
            return None
        return lists[0]["id"]
    except Exception:
        return None


def pull_tasks(tasklist_id: str, show_completed: bool = False) -> list[dict]:
    try:
        client = _get_tasks_client()
        result = client.tasks().list(
            tasklist=tasklist_id,
            showCompleted=show_completed,
            showHidden=False,
        ).execute()
        return result.get("items", [])
    except Exception:
        return []


def push_task(
    tasklist_id: str,
    title: str,
    notes: str = None,
    due: str = None,
) -> dict | None:
    try:
        client = _get_tasks_client()
        body = {"title": title}
        if notes:
            body["notes"] = notes
        if due:
            body["due"] = due + "T00:00:00.000Z"
        return client.tasks().insert(tasklist=tasklist_id, body=body).execute()
    except Exception:
        return None


def complete_task(tasklist_id: str, google_task_id: str) -> bool:
    try:
        client = _get_tasks_client()
        client.tasks().patch(
            tasklist=tasklist_id,
            task=google_task_id,
            body={"status": "completed"},
        ).execute()
        return True
    except Exception:
        return False


def delete_task(tasklist_id: str, google_task_id: str) -> bool:
    try:
        client = _get_tasks_client()
        client.tasks().delete(
            tasklist=tasklist_id,
            task=google_task_id,
        ).execute()
        return True
    except Exception:
        return False
