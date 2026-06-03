"""Google Tasks API client — raw API calls only."""

import logging

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from api.google.youtube_api import _get_credentials
from api._handler import BaseAPIHandler

logger = logging.getLogger("privy.tasks_api")

DEFAULT_TASKLIST = "@default"


class TasksAPIHandler(BaseAPIHandler):
    """Google Tasks API handler with caching for reads, direct writes."""
    
    CACHE_PREFIX = "google_tasks"
    
    def _get_client(self):
        creds = _get_credentials()
        return build("tasks", "v1", credentials=creds, cache_discovery=False)
    
    # ─── READ OPERATIONS (use self.call) ──
    
    def get_default_tasklist_id(self) -> dict:
        def _live() -> dict:
            client = self._get_client()
            result = client.tasklists().list(maxResults=10).execute()
            lists = result.get("items", [])
            if not lists:
                return {"tasklist_id": None}
            return {"tasklist_id": lists[0]["id"]}
        
        return self.call("tasklist_id", self.hash(), _live, stale_ok=True)
    
    def pull_tasks(self, tasklist_id: str, show_completed: bool = False) -> dict:
        params_hash = self.hash(tasklist_id, show_completed)
        
        def _live() -> dict:
            client = self._get_client()
            result = client.tasks().list(
                tasklist=tasklist_id,
                showCompleted=show_completed,
                showHidden=False,
            ).execute()
            return {"tasks": result.get("items", []), "tasklist_id": tasklist_id}
        
        return self.call("tasks", params_hash, _live, stale_ok=True)
    
    # ─── WRITE OPERATIONS (direct, no cache) ─
    
    def push_task(self, tasklist_id: str, title: str, notes: str = None, due: str = None) -> dict | None:
        """Direct write — no cache, no stale."""
        try:
            client = self._get_client()
            body = {"title": title}
            if notes:
                body["notes"] = notes
            if due:
                body["due"] = due + "T00:00:00.000Z"
            return client.tasks().insert(tasklist=tasklist_id, body=body).execute()
        except Exception as e:
            logger.warning(f"[tasks] push_task failed: {e}")
            return None
    
    def complete_task(self, tasklist_id: str, google_task_id: str) -> bool:
        """Direct write — no cache, no stale."""
        try:
            client = self._get_client()
            client.tasks().patch(
                tasklist=tasklist_id,
                task=google_task_id,
                body={"status": "completed"},
            ).execute()
            return True
        except Exception as e:
            logger.warning(f"[tasks] complete_task failed: {e}")
            return False
    
    def delete_task(self, tasklist_id: str, google_task_id: str) -> bool:
        """Direct write — no cache, no stale."""
        try:
            client = self._get_client()
            request = client.tasks().delete(tasklist=tasklist_id, task=google_task_id)
            response = request.execute()
            # Google Tasks DELETE returns 204 No Content on success
            # execute() returns None or empty string for 204, raises HttpError for failures
            # Both None and "" are success cases
            return response is None or response == ""
        except HttpError as e:
            # HttpError is raised for non-2xx status codes
            logger.warning(f"[tasks] delete_task failed with HTTP {e.resp.status}: {e}")
            return False
        except Exception as e:
            logger.warning(f"[tasks] delete_task failed: {e}")
            return False

    def update_task(self, tasklist_id: str, google_task_id: str, title: str = None, notes: str = None, due: str = None, status: str = None) -> dict | None:
        """Update existing task in Google Tasks. Direct write — no cache, no stale."""
        try:
            client = self._get_client()
            body = {}
            if title:
                body["title"] = title
            if notes:
                body["notes"] = notes
            if due:
                body["due"] = due + "T00:00:00.000Z"
            if status:
                body["status"] = status
            return client.tasks().patch(
                tasklist=tasklist_id,
                task=google_task_id,
                body=body,
            ).execute()
        except Exception as e:
            logger.warning(f"[tasks] update_task failed: {e}")
            return None


# Module-level instance
tasks_api = TasksAPIHandler()

# Backwards compat
def get_default_tasklist_id():
    return tasks_api.get_default_tasklist_id()

def pull_tasks(tasklist_id, show_completed=False):
    return tasks_api.pull_tasks(tasklist_id, show_completed)

def push_task(tasklist_id, title, notes=None, due=None):
    return tasks_api.push_task(tasklist_id, title, notes, due)

def complete_task(tasklist_id, google_task_id):
    return tasks_api.complete_task(tasklist_id, google_task_id)

def delete_task(tasklist_id, google_task_id):
    return tasks_api.delete_task(tasklist_id, google_task_id)

def update_task(tasklist_id, google_task_id, title=None, notes=None, due=None, status=None):
    return tasks_api.update_task(tasklist_id, google_task_id, title, notes, due, status)

# Backwards compat for test imports
def _get_tasks_client():
    return tasks_api._get_client()
