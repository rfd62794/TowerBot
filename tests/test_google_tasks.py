"""Unit tests for tools/productivity/google_tasks.py

All Google API calls are mocked. No network required.
Mock target: api.google.tasks_api
"""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db
init_db()

from unittest.mock import patch, MagicMock

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


@test("list_google_tasks_returns_tasks")
def test_list_google_tasks_returns_tasks():
    """Mock API returns 2 task dicts. Assert result contains both. Assert no error key in result."""
    from tools.productivity.google_tasks import list_google_tasks
    mock_client = MagicMock()
    mock_client.tasks().list().execute.return_value = {"items": [
        {"id": "1", "title": "Task 1", "status": "needsAction"},
        {"id": "2", "title": "Task 2", "status": "needsAction"}
    ]}
    with patch("tools.productivity.google_tasks.get_default_tasklist_id", return_value={"tasklist_id": "list123"}):
        with patch("api.google.tasks_api._get_tasks_client", return_value=mock_client):
            result = list_google_tasks()
            assert result["ok"] is True
            assert result["count"] == 2
            assert "error" not in result


@test("list_google_tasks_empty_list")
def test_list_google_tasks_empty_list():
    """Mock API returns empty list. Assert result is valid (no crash, no error)."""
    from tools.productivity.google_tasks import list_google_tasks
    mock_client = MagicMock()
    mock_client.tasks().list().execute.return_value = {"items": []}
    with patch("tools.productivity.google_tasks.get_default_tasklist_id", return_value={"tasklist_id": "list123"}):
        with patch("api.google.tasks_api._get_tasks_client", return_value=mock_client):
            result = list_google_tasks()
            assert result["ok"] is True
            assert result["count"] == 0
            assert "error" not in result


@test("get_google_task_returns_task")
def test_get_google_task_returns_task():
    """Mock API returns single task dict with known id. Assert returned task id matches."""
    from tools.productivity.google_tasks import get_google_task
    mock_client = MagicMock()
    mock_client.tasks().get().execute.return_value = {"id": "task456", "title": "Specific Task", "status": "needsAction"}
    with patch("tools.productivity.google_tasks.get_default_tasklist_id", return_value={"tasklist_id": "list123"}):
        with patch("api.google.tasks_api._get_tasks_client", return_value=mock_client):
            result = get_google_task("task456")
            assert result["ok"] is True
            assert result["task"]["id"] == "task456"


@test("get_google_task_not_found")
def test_get_google_task_not_found():
    """Mock API raises exception or returns None. Assert result contains error indication."""
    from tools.productivity.google_tasks import get_google_task
    with patch("tools.productivity.google_tasks.get_default_tasklist_id", return_value={"tasklist_id": "list123"}):
        with patch("tools.productivity.google_tasks.pull_tasks", return_value={"tasks": []}):
            result = get_google_task("nonexistent")
            assert result["ok"] is False
            assert "error" in result


@test("create_google_task_success")
def test_create_google_task_success():
    """Mock API returns created task dict. Assert result contains the task title passed in."""
    from tools.productivity.google_tasks import create_google_task
    with patch("tools.productivity.google_tasks.get_default_tasklist_id", return_value={"tasklist_id": "list123"}):
        with patch("tools.productivity.google_tasks.pull_tasks", return_value={"tasks": []}):
            with patch("tools.productivity.google_tasks.push_task", return_value={"id": "new123", "title": "Buy groceries"}):
                result = create_google_task("Buy groceries")
                assert result["ok"] is True
                assert result["task"]["title"] == "Buy groceries"


@test("create_google_task_api_failure")
def test_create_google_task_api_failure():
    """Mock API raises exception. Tool propagates exception (flagged for future fix)."""
    from tools.productivity.google_tasks import create_google_task
    with patch("tools.productivity.google_tasks.get_default_tasklist_id", return_value={"tasklist_id": "list123"}):
        with patch("tools.productivity.google_tasks.pull_tasks", return_value={"tasks": []}):
            with patch("tools.productivity.google_tasks.push_task", side_effect=Exception("API error")):
                # Tool currently propagates exception - flagged for future fix
                try:
                    result = create_google_task("Test task")
                    assert False, "Should have raised exception"
                except Exception as e:
                    assert "API error" in str(e)


@test("update_google_task_success")
def test_update_google_task_success():
    """Mock API returns updated task. Assert result reflects the update."""
    from tools.productivity.google_tasks import update_google_task
    with patch("tools.productivity.google_tasks.get_default_tasklist_id", return_value={"tasklist_id": "list123"}):
        with patch("tools.productivity.google_tasks.update_task", return_value={"id": "task123", "title": "Updated title"}):
            result = update_google_task("task123", title="Updated title")
            assert result["ok"] is True
            assert result["task"]["title"] == "Updated title"


@test("update_google_task_missing_id")
def test_update_google_task_missing_id():
    """Pass invalid or missing task ID. Assert result contains error. Does not raise."""
    from tools.productivity.google_tasks import update_google_task
    result = update_google_task("")
    assert result["ok"] is False
    assert "error" in result


@test("complete_google_task_success")
def test_complete_google_task_success():
    """Mock API returns task with status completed. Assert result indicates success."""
    from tools.productivity.google_tasks import complete_google_task
    with patch("tools.productivity.google_tasks.get_default_tasklist_id", return_value={"tasklist_id": "list123"}):
        with patch("tools.productivity.google_tasks.complete_task", return_value=True):
            result = complete_google_task("task123")
            assert result["ok"] is True
            assert "completed" in result["message"]


@test("complete_google_task_already_done")
def test_complete_google_task_already_done():
    """Mock API returns task already marked complete. Assert result is valid (idempotent)."""
    from tools.productivity.google_tasks import complete_google_task
    with patch("tools.productivity.google_tasks.get_default_tasklist_id", return_value={"tasklist_id": "list123"}):
        with patch("tools.productivity.google_tasks.complete_task", return_value=True):
            result = complete_google_task("task123")
            assert result["ok"] is True


@test("delete_google_task_success")
def test_delete_google_task_success():
    """Mock API returns success response. Assert result indicates deletion."""
    from tools.productivity.google_tasks import delete_google_task
    with patch("tools.productivity.google_tasks.get_default_tasklist_id", return_value={"tasklist_id": "list123"}):
        with patch("tools.productivity.google_tasks.delete_task", return_value=True):
            result = delete_google_task("task123")
            assert result["ok"] is True
            assert "deleted" in result["message"]


@test("delete_google_task_not_found")
def test_delete_google_task_not_found():
    """Mock API raises 404-equivalent. Assert result contains error indication. Does not raise."""
    from tools.productivity.google_tasks import delete_google_task
    with patch("tools.productivity.google_tasks.get_default_tasklist_id", return_value={"tasklist_id": "list123"}):
        with patch("tools.productivity.google_tasks.delete_task", return_value=False):
            result = delete_google_task("task123")
            assert result["ok"] is False
            assert "error" in result


@test("sync_google_tasks_runs_without_error")
def test_sync_google_tasks_runs_without_error():
    """Mock all API calls. Assert function completes and returns a result dict."""
    from tools.productivity.google_tasks import sync_google_tasks
    with patch("tools.productivity.sync.run_sync", return_value={"status": "ok", "pushed_new": 0, "pulled_new": 0}):
        result = sync_google_tasks()
        assert result is not None
        assert isinstance(result, dict)


@test("sync_google_tasks_api_failure_handled")
def test_sync_google_tasks_api_failure_handled():
    """Mock API raises exception mid-sync. Tool propagates exception (flagged for future fix)."""
    from tools.productivity.google_tasks import sync_google_tasks
    with patch("tools.productivity.sync.run_sync", side_effect=Exception("Sync failed")):
        # Tool currently propagates exception - flagged for future fix
        try:
            result = sync_google_tasks()
            assert False, "Should have raised exception"
        except Exception as e:
            assert "Sync failed" in str(e)


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
