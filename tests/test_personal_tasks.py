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

from datetime import datetime

TESTS = []
_TEST_START = None


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def _teardown():
    """Remove test personal tasks so they don't show up in heartbeat reminders."""
    try:
        from infra.db.schema import _exec
        if _TEST_START:
            _exec(
                "DELETE FROM personal_tasks WHERE created_at >= ?",
                (_TEST_START,),
                commit=True,
            )
            _exec(
                "DELETE FROM task_reminders WHERE task_id NOT IN "
                "(SELECT id FROM personal_tasks)",
                commit=True,
            )
    except Exception:
        pass


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    global _TEST_START
    _TEST_START = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    from tools.productivity.personal import list_personal_tasks
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
    from datetime import datetime, timedelta
    today = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")  # Use tomorrow to avoid collision
    unique_title = f"Daily standup {datetime.now().strftime('%H%M%S')}"
    task_id = add_personal_task(
        unique_title,
        due_date=today,
        recurrence="daily",
    )
    result = complete_personal_task(task_id)
    assert result.get("status") == "completed"
    assert result.get("next_due") is not None, f"Expected next_due for recurring task, got {result.get('next_due')}"
    all_tasks = get_personal_tasks(filter="all")
    titles = [t["title"] for t in all_tasks]
    assert unique_title in titles, "Expected recurring task re-inserted"


@test("personal: snooze pushes due_datetime forward")
def test_snooze():
    from infra.db.personal_tasks import add_personal_task, snooze_personal_task
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    unique_title = f"Snooze me {datetime.now().strftime('%H%M%S')}"
    task_id = add_personal_task(unique_title, due_date=today, due_time="09:00")
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
    from tools.productivity.personal import parse_natural_deadline
    from datetime import datetime, timedelta
    result = parse_natural_deadline("tomorrow")
    expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert result["date"] == expected, f"Expected {expected}, got {result['date']}"
    assert result["time"] is None


@test("personal: parse_natural_deadline 'Friday at 6PM' works")
def test_parse_friday_6pm():
    from tools.productivity.personal import parse_natural_deadline
    from datetime import datetime, timedelta
    result = parse_natural_deadline("Friday at 6PM")
    assert result["date"] is not None, "Expected a date"
    assert result["time"] == "18:00", f"Expected 18:00, got {result['time']}"
    parsed = datetime.strptime(result["date"], "%Y-%m-%d")
    assert parsed.weekday() == 4, "Expected Friday (weekday=4)"


@test("personal: parse_recurrence 'every Monday' works")
def test_parse_recurrence_weekly():
    from tools.productivity.personal import parse_recurrence
    result = parse_recurrence("every Monday")
    assert result == "weekly:monday", f"Expected 'weekly:monday', got {result}"


@test("personal: parse_recurrence 'every day' works")
def test_parse_recurrence_daily():
    from tools.productivity.personal import parse_recurrence
    result = parse_recurrence("every day")
    assert result == "daily", f"Expected 'daily', got {result}"


@test("personal: next_recurrence_date daily adds 1 day")
def test_next_recurrence_date_daily():
    from infra.db.personal_tasks import next_recurrence_date
    from datetime import datetime, timedelta
    anchor = datetime.now().strftime("%Y-%m-%d")
    result = next_recurrence_date("daily", anchor)
    expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert result == expected, f"Expected {expected}, got {result}"


@test("personal: next_recurrence_date weekly:wednesday from wednesday adds 7 days")
def test_next_recurrence_date_weekly_same_day():
    from infra.db.personal_tasks import next_recurrence_date
    from datetime import datetime, timedelta
    # Create a Wednesday anchor
    wednesday = datetime(2026, 5, 27)  # Wednesday
    anchor = wednesday.strftime("%Y-%m-%d")
    result = next_recurrence_date("weekly:wednesday", anchor)
    expected = (wednesday + timedelta(days=7)).strftime("%Y-%m-%d")
    assert result == expected, f"Expected {expected}, got {result}"


@test("personal: next_recurrence_date unknown format falls back to tomorrow")
def test_next_recurrence_date_unknown():
    from infra.db.personal_tasks import next_recurrence_date
    from datetime import datetime, timedelta
    anchor = datetime.now().strftime("%Y-%m-%d")
    result = next_recurrence_date("gibberish", anchor)
    expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert result == expected, f"Expected {expected}, got {result}"


@test("personal: push_missed_tasks pushes non-recurring to tomorrow")
def test_push_missed_tasks_non_recurring():
    from infra.db.personal_tasks import add_personal_task, push_missed_tasks, get_personal_tasks
    from datetime import datetime, timedelta
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    task_id = add_personal_task("Missed non-recurring", due_date=yesterday)
    pushed = push_missed_tasks()
    
    assert len(pushed) > 0, "Expected at least one pushed task"
    found = any(t["id"] == task_id for t in pushed)
    assert found, "Expected task to be in pushed list"
    
    # Verify due_date updated
    task = get_personal_tasks(filter="all")
    updated = [t for t in task if t["id"] == task_id][0]
    assert updated["due_date"] == tomorrow, f"Expected due_date {tomorrow}, got {updated['due_date']}"


@test("personal: push_missed_tasks handles collision with existing pending task")
def test_push_missed_tasks_collision():
    from infra.db.personal_tasks import add_personal_task, push_missed_tasks, get_personal_tasks
    from datetime import datetime, timedelta
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Create collision: missed task + future task with same title/date
    missed_id = add_personal_task("Collision test", due_date=yesterday)
    future_id = add_personal_task("Collision test", due_date=tomorrow)
    
    pushed = push_missed_tasks()
    
    # Missed task should be deleted (collision), future task untouched
    tasks = get_personal_tasks(filter="all")
    task_ids = [t["id"] for t in tasks]
    assert missed_id not in task_ids, "Missed task should be deleted on collision"
    assert future_id in task_ids, "Future task should remain"
    
    # Still should be in pushed list (nudge queued)
    found = any(t["id"] == missed_id for t in pushed)
    assert found, "Deleted task should still be in pushed list for nudge"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
