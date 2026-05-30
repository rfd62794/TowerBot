"""Tests for personal task system — DB, tools, and parsers."""

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


_TEST_TASK_TITLES = [
    "Test dentist call", "Filter test task", "Dentist at 10am",
    "Test task for snooze", "Due soon task",
]


def _teardown():
    """Remove test personal tasks so they don't show up in heartbeat reminders."""
    try:
        from infra.db.schema import _exec
        for title in _TEST_TASK_TITLES:
            _exec("DELETE FROM personal_tasks WHERE title = ?", (title,), commit=True)
        _exec(
            "DELETE FROM task_reminders WHERE task_id NOT IN "
            "(SELECT id FROM personal_tasks)",
            commit=True,
        )
    except Exception:
        pass


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    result = _run(TESTS)
    _teardown()
    return result


@test("personal: personal_tasks table exists")
def test_table_exists():
    from infra.db.schema import _exec
    row = _exec(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='personal_tasks'"
    ).fetchone()
    assert row is not None, "personal_tasks table missing"


@test("personal: task_reminders table exists")
def test_reminders_table_exists():
    from infra.db.schema import _exec
    row = _exec(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='task_reminders'"
    ).fetchone()
    assert row is not None, "task_reminders table missing"


@test("personal: add_personal_task creates entry")
def test_add_task():
    from infra.db.personal_tasks import add_personal_task, get_personal_tasks
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    task_id = add_personal_task("Test dentist call", due_date=today)
    assert isinstance(task_id, int) and task_id > 0
    tasks = get_personal_tasks(filter="today")
    ids = [t["id"] for t in tasks]
    assert task_id in ids


@test("personal: add_personal_task with recurrence")
def test_add_task_recurrence():
    from infra.db.personal_tasks import add_personal_task
    task_id = add_personal_task(
        "YouTube analytics review",
        recurrence="weekly:monday",
    )
    assert isinstance(task_id, int) and task_id > 0


@test("personal: list_personal_tasks today filter works")
def test_list_today():
    from infra.db.personal_tasks import add_personal_task
    from tools.personal import list_personal_tasks
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    add_personal_task("Filter test task", due_date=today)
    result = list_personal_tasks(filter="today")
    assert isinstance(result, dict)
    assert "count" in result and "tasks" in result
    assert result["count"] >= 1
    assert result["filter"] == "today"


@test("personal: complete_personal_task marks done")
def test_complete_task():
    from infra.db.personal_tasks import add_personal_task, complete_personal_task
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    task_id = add_personal_task("Complete me task", due_date=today)
    result = complete_personal_task(task_id)
    assert result.get("status") == "completed"
    assert result.get("id") == task_id
    assert result.get("next_due") is None


@test("personal: complete_personal_task recurring generates next occurrence")
def test_complete_recurring():
    from infra.db.personal_tasks import (
        add_personal_task, complete_personal_task, get_personal_tasks
    )
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    task_id = add_personal_task(
        "Daily standup",
        due_date=today,
        recurrence="daily",
    )
    result = complete_personal_task(task_id)
    assert result.get("status") == "completed"
    assert result.get("next_due") is not None, "Expected next_due for recurring task"
    all_tasks = get_personal_tasks(filter="all")
    titles = [t["title"] for t in all_tasks]
    assert "Daily standup" in titles, "Expected recurring task re-inserted"


@test("personal: snooze pushes due_datetime forward")
def test_snooze():
    from infra.db.personal_tasks import add_personal_task, snooze_personal_task
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    task_id = add_personal_task("Snooze me", due_date=today, due_time="09:00")
    result = snooze_personal_task(task_id, minutes=60)
    assert result.get("status") == "snoozed"
    assert result.get("id") == task_id
    assert "new_due" in result
    assert "10:00" in result["new_due"]


@test("personal: get_tasks_due_soon returns correct window")
def test_tasks_due_soon():
    from infra.db.personal_tasks import add_personal_task, get_tasks_due_soon
    from datetime import datetime, timedelta
    soon = datetime.now() + timedelta(minutes=30)
    due_date = soon.strftime("%Y-%m-%d")
    due_time = soon.strftime("%H:%M")
    task_id = add_personal_task("Due soon task", due_date=due_date, due_time=due_time)
    tasks = get_tasks_due_soon(minutes=90)
    ids = [t["id"] for t in tasks]
    assert task_id in ids, "Task due in 30 min not in 90-min window"


@test("personal: parse_natural_deadline 'tomorrow' works")
def test_parse_tomorrow():
    from tools.personal import parse_natural_deadline
    from datetime import datetime, timedelta
    result = parse_natural_deadline("tomorrow")
    expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert result["date"] == expected, f"Expected {expected}, got {result['date']}"
    assert result["time"] is None


@test("personal: parse_natural_deadline 'Friday at 6PM' works")
def test_parse_friday_6pm():
    from tools.personal import parse_natural_deadline
    from datetime import datetime, timedelta
    result = parse_natural_deadline("Friday at 6PM")
    assert result["date"] is not None, "Expected a date"
    assert result["time"] == "18:00", f"Expected 18:00, got {result['time']}"
    parsed = datetime.strptime(result["date"], "%Y-%m-%d")
    assert parsed.weekday() == 4, "Expected Friday (weekday=4)"


@test("personal: parse_recurrence 'every Monday' works")
def test_parse_recurrence_weekly():
    from tools.personal import parse_recurrence
    result = parse_recurrence("every Monday")
    assert result == "weekly:monday", f"Expected 'weekly:monday', got {result}"


@test("personal: parse_recurrence 'every day' works")
def test_parse_recurrence_daily():
    from tools.personal import parse_recurrence
    result = parse_recurrence("every day")
    assert result == "daily", f"Expected 'daily', got {result}"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
