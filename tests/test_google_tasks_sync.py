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
    from tools.api.google_tasks_api import _get_tasks_client
    client = _get_tasks_client()
    assert client is not None


@test("sync: get_default_tasklist_id returns dict with tasklist_id")
def test_tasklist_id():
    from tools.api.google_tasks_api import get_default_tasklist_id
    result = get_default_tasklist_id()
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "tasklist_id" in result, "Missing 'tasklist_id' key"
    assert isinstance(result["tasklist_id"], str) or result["tasklist_id"] is None, \
        f"Expected str or None for tasklist_id, got {result['tasklist_id']!r}"


@test("sync: pull_tasks returns dict with tasks")
def test_pull_tasks():
    from tools.api.google_tasks_api import get_default_tasklist_id, pull_tasks
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
    from tools.api.google_tasks_api import (
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


@test("sync: run_sync returns status ok")
def test_run_sync():
    from tools.productivity.sync import run_sync
    result = run_sync()
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result.get("status") == "ok", \
        f"Expected status='ok', got {result}"


@test("sync: pull_from_google returns int")
def test_pull_from_google():
    from tools.productivity.sync import pull_from_google
    result = pull_from_google()
    assert isinstance(result, int), f"Expected int, got {type(result)}"


@test("sync: push_new_tasks returns int")
def test_push_new_tasks():
    from tools.productivity.sync import push_new_tasks
    result = push_new_tasks()
    assert isinstance(result, int), f"Expected int, got {type(result)}"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
