"""Tests for autonomous task runner — DB + scheduler."""

import sys
import os
import time

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


@test("autonomous: agent_actions table exists")
def test_table_exists():
    from infra.db.schema import _exec
    result = _exec("SELECT name FROM sqlite_master WHERE type='table' AND name='agent_actions'").fetchall()
    assert len(result) > 0, "agent_actions table not found"


@test("autonomous: idx_agent_actions_ran index exists")
def test_index_exists():
    from infra.db.schema import _exec
    result = _exec("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_agent_actions_ran'").fetchall()
    assert len(result) > 0, "idx_agent_actions_ran index not found"


@test("autonomous: record_agent_action creates entry")
def test_record_action():
    from infra.db import record_agent_action, get_overnight_actions
    record_agent_action("test_task", "DONE: test result", 100, 0)
    actions = get_overnight_actions()
    assert len(actions) > 0, "No actions recorded"
    assert actions[0]["task_name"] == "test_task", f"Expected test_task, got {actions[0]['task_name']}"
    assert actions[0]["result"] == "DONE: test result", f"Expected 'DONE: test result', got {actions[0]['result']}"


@test("autonomous: get_overnight_actions returns entries from last 8h")
def test_get_overnight():
    from infra.db import record_agent_action, get_overnight_actions
    record_agent_action("test_task_recent", "DONE: recent", 50, 0)
    actions = get_overnight_actions()
    assert len(actions) > 0, "No overnight actions returned"
    # Should include the recent entry
    task_names = [a["task_name"] for a in actions]
    assert "test_task_recent" in task_names, "Recent task not in overnight actions"


@test("autonomous: get_overnight_actions excludes entries older than 8h")
def test_exclude_old():
    from infra.db import record_agent_action, get_overnight_actions
    from infra.db.schema import _exec
    # Insert an old entry manually
    old_time = "2020-01-01 00:00:00"
    _exec(
        "INSERT INTO agent_actions (task_name, ran_at, result, duration_ms, urgent) VALUES (?, ?, ?, ?, ?)",
        ("old_task", old_time, "DONE: old", 100, 0),
        commit=True
    )
    actions = get_overnight_actions()
    task_names = [a["task_name"] for a in actions]
    assert "old_task" not in task_names, "Old task should be excluded from overnight actions"


@test("autonomous: urgent=1 when result starts with URGENT:")
def test_urgent_flag():
    from infra.db import record_agent_action, get_overnight_actions
    record_agent_action("urgent_task", "URGENT: something happened", 200, 0)
    actions = get_overnight_actions()
    urgent_tasks = [a for a in actions if a["task_name"] == "urgent_task"]
    assert len(urgent_tasks) > 0, "Urgent task not recorded"
    assert urgent_tasks[0]["urgent"] == 1, f"Expected urgent=1, got {urgent_tasks[0]['urgent']}"


@test("autonomous: setup_autonomous_scheduler registers 3 jobs")
def test_scheduler_jobs():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from bot.autonomous import setup_autonomous_scheduler
    scheduler = AsyncIOScheduler()
    setup_autonomous_scheduler(scheduler, lambda x: None)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 3, f"Expected 3 jobs, got {len(jobs)}"


@test("autonomous: TASKS dict has 3 enabled tasks")
def test_tasks_dict():
    from bot.autonomous import TASKS
    assert len(TASKS) == 3, f"Expected 3 tasks, got {len(TASKS)}"
    enabled = [name for name, task in TASKS.items() if task.get("enabled")]
    assert len(enabled) == 3, f"Expected 3 enabled tasks, got {len(enabled)}"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
