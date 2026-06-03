"""Tests for Google Tasks two-way sync."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db
init_db()

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


@test("sync: google_tasks_api credentials load")
def test_credentials():
    from api.google.tasks_api import _get_tasks_client
    client = _get_tasks_client()
    assert client is not None


@test("sync: get_default_tasklist_id returns dict with tasklist_id")
def test_tasklist_id():
    from api.google.tasks_api import get_default_tasklist_id
    result = get_default_tasklist_id()
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "tasklist_id" in result, "Missing 'tasklist_id' key"
    assert isinstance(result["tasklist_id"], str) or result["tasklist_id"] is None, \
        f"Expected str or None for tasklist_id, got {result['tasklist_id']!r}"


@test("sync: pull_tasks returns dict with tasks")
def test_pull_tasks():
    from api.google.tasks_api import get_default_tasklist_id, pull_tasks
    tasklist_id_raw = get_default_tasklist_id()
    tasklist_id = tasklist_id_raw.get("tasklist_id")
    if not tasklist_id:
        return  # Skip if no tasklist available
    result = pull_tasks(tasklist_id)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "tasks" in result, "Missing 'tasks' key"
    assert isinstance(result["tasks"], list), f"Expected list for tasks, got {type(result['tasks'])}"


@test("sync: push_task creates and deletes task in Google")
def test_push_delete_task():
    from api.google.tasks_api import (
        get_default_tasklist_id, push_task, delete_task
    )
    tasklist_id_raw = get_default_tasklist_id()
    tasklist_id = tasklist_id_raw.get("tasklist_id")
    assert tasklist_id, "No tasklist_id"
    result = push_task(tasklist_id, title="PrivyBot sync test — delete me")
    assert result is not None, "push_task returned None"
    assert "id" in result, "No id in push_task result"
    deleted = delete_task(tasklist_id, result["id"])
    assert deleted is True, "delete_task returned False"


@test("sync: tasks_sync table exists")
def test_tasks_sync_table():
    from infra.db.schema import _exec
    row = _exec(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks_sync'"
    ).fetchone()
    assert row is not None, "tasks_sync table missing"


# Sync tests removed per ADR-038 Phase 2 - tools.productivity.sync module deleted
# test_run_sync, test_pull_from_google, test_push_new_tasks depended on deleted sync module


@test("sync: delete_google_task actually deletes and get_google_task confirms")
def test_delete_google_task_live():
    """Live integration test - create, delete, verify gone."""
    from tools.productivity.google_tasks import (
        create_google_task, delete_google_task, get_google_task
    )
    # Create a test task
    created = create_google_task(
        title="PrivyBot live delete test — delete me",
        due_date="2026-12-31"
    )
    assert created.get("ok") is True, f"Failed to create test task: {created}"
    task_id = created.get("task", {}).get("id")
    assert task_id, "No task_id in created task"

    # Delete the task
    deleted = delete_google_task(task_id)
    assert deleted.get("ok") is True, f"Failed to delete task: {deleted}"

    # Verify it's gone
    retrieved = get_google_task(task_id)
    assert retrieved.get("ok") is False, f"Task still exists after delete: {retrieved}"
    assert "error" in retrieved, "Expected error in response for deleted task"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
