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


@test("autonomous: setup_autonomous_scheduler registers jobs")
def test_scheduler_jobs():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from bot.autonomous import setup_autonomous_scheduler
    scheduler = AsyncIOScheduler()
    async def mock_send(x):
        pass
    setup_autonomous_scheduler(scheduler, mock_send)
    jobs = scheduler.get_jobs()
    assert len(jobs) > 0, f"Expected at least 1 job, got {len(jobs)}"


@test("autonomous: get_all_resolved_tasks returns 6 enabled tasks")
def test_tasks_dict():
    from bot.task_runner import get_all_resolved_tasks
    tasks = get_all_resolved_tasks()
    assert len(tasks) == 6, f"Expected 6 tasks, got {len(tasks)}"


@test("autonomous: setup_template_scheduler registers template jobs")
def test_template_scheduler_registers():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from bot.autonomous import setup_template_scheduler
    scheduler = AsyncIOScheduler()
    async def mock_send(x):
        pass
    setup_template_scheduler(scheduler, mock_send)
    jobs = scheduler.get_jobs()
    # Should have at least the hourly_fact template job
    template_jobs = [j for j in jobs if j.id.startswith("template_")]
    assert len(template_jobs) >= 1, f"Expected at least 1 template job, got {len(template_jobs)}"


@test("autonomous: setup_template_scheduler skips non-schedule templates")
def test_template_scheduler_skips_non_schedule():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from bot.autonomous import setup_template_scheduler
    from unittest.mock import patch
    scheduler = AsyncIOScheduler()
    async def mock_send(x):
        pass
    # Mock list_templates to return a template without trigger.type=schedule
    with patch("bot.autonomous.list_templates", return_value=[
        {"name": "test_no_trigger", "source": "canonical", "version": "1.0", "description": ""}
    ]):
        with patch("bot.autonomous.load_template", return_value={
            "name": "test_no_trigger",
            "trigger": {"type": "manual"},
            "steps": []
        }):
            setup_template_scheduler(scheduler, mock_send)
    jobs = scheduler.get_jobs()
    template_jobs = [j for j in jobs if j.id.startswith("template_")]
    assert len(template_jobs) == 0, f"Expected 0 template jobs for non-schedule trigger, got {len(template_jobs)}"


@test("autonomous: run_scheduled_template loads and creates chain")
def test_run_scheduled_template_loads():
    from bot.autonomous import run_scheduled_template
    from unittest.mock import patch, AsyncMock
    async def mock_send(x):
        pass
    # Mock template loading and chain creation
    with patch("bot.autonomous.load_template", return_value={
        "name": "test_template",
        "trigger": {"type": "schedule", "interval_minutes": 60},
        "steps": []
    }):
        with patch("bot.autonomous.create_chain", return_value="chain_123"):
            with patch("bot.autonomous.ChainRunner") as mock_runner:
                mock_runner_instance = mock_runner.return_value
                mock_runner_instance.run.return_value = {"status": "complete"}
                # Run the function
                import asyncio
                asyncio.run(run_scheduled_template("test_template", mock_send))
                # Verify chain was created
                assert mock_runner_instance.run.called, "ChainRunner.run should have been called"


@test("autonomous: _notify sends message with correct prefix")
def test_notify_sends_message():
    from bot.autonomous import _notify
    from unittest.mock import AsyncMock
    mock_send = AsyncMock()
    import asyncio
    asyncio.run(_notify("Test message", mock_send))
    assert mock_send.called, "send function should have been called"
    call_args = mock_send.call_args[0][0]
    assert call_args.startswith("💡 "), f"Expected 💡 prefix, got: {call_args}"


@test("autonomous: _notify urgent uses red prefix")
def test_notify_urgent_uses_red_prefix():
    from bot.autonomous import _notify
    from unittest.mock import AsyncMock
    mock_send = AsyncMock()
    import asyncio
    asyncio.run(_notify("Urgent message", mock_send, urgent=True))
    assert mock_send.called, "send function should have been called"
    call_args = mock_send.call_args[0][0]
    assert call_args.startswith("🔴 "), f"Expected 🔴 prefix, got: {call_args}"


@test("autonomous: _notify failure does not crash")
def test_notify_failure_does_not_crash():
    from bot.autonomous import _notify
    from unittest.mock import AsyncMock
    mock_send = AsyncMock(side_effect=Exception("Send failed"))
    import asyncio
    # Should not raise
    asyncio.run(_notify("Test message", mock_send))


@test("autonomous: community_scout notifies above threshold")
def test_community_scout_notifies_above_threshold():
    from bot.autonomous import run_scheduled_template
    from unittest.mock import patch, AsyncMock
    async def mock_send(x):
        pass
    with patch("bot.autonomous.load_template", return_value={
        "name": "community_scout",
        "trigger": {"type": "schedule", "interval_minutes": 60},
        "steps": []
    }):
        with patch("bot.autonomous.create_chain", return_value="chain_123"):
            with patch("bot.autonomous.ChainRunner") as mock_runner:
                mock_runner_instance = mock_runner.return_value
                mock_runner_instance.run.return_value = {
                    "status": "complete",
                    "upvotes": 25,
                    "title": "Test thread",
                    "url": "https://example.com"
                }
                with patch("bot.autonomous._notify", new_callable=AsyncMock) as mock_notify:
                    import asyncio
                    asyncio.run(run_scheduled_template("community_scout", mock_send))
                    assert mock_notify.called, "_notify should have been called for upvotes >= 20"


@test("autonomous: community_scout silent below threshold")
def test_community_scout_silent_below_threshold():
    from bot.autonomous import run_scheduled_template
    from unittest.mock import patch, AsyncMock
    async def mock_send(x):
        pass
    with patch("bot.autonomous.load_template", return_value={
        "name": "community_scout",
        "trigger": {"type": "schedule", "interval_minutes": 60},
        "steps": []
    }):
        with patch("bot.autonomous.create_chain", return_value="chain_123"):
            with patch("bot.autonomous.ChainRunner") as mock_runner:
                mock_runner_instance = mock_runner.return_value
                mock_runner_instance.run.return_value = {
                    "status": "complete",
                    "upvotes": 10,
                    "title": "Test thread",
                    "url": "https://example.com"
                }
                with patch("bot.autonomous._notify", new_callable=AsyncMock) as mock_notify:
                    import asyncio
                    asyncio.run(run_scheduled_template("community_scout", mock_send))
                    assert not mock_notify.called, "_notify should not have been called for upvotes < 20"


@test("autonomous: blog draft notifies on completion")
def test_blog_draft_notifies_on_completion():
    from bot.autonomous import run_scheduled_template
    from unittest.mock import patch, AsyncMock
    async def mock_send(x):
        pass
    with patch("bot.autonomous.load_template", return_value={
        "name": "blog_scaffold",
        "trigger": {"type": "schedule", "interval_minutes": 60},
        "steps": []
    }):
        with patch("bot.autonomous.create_chain", return_value="chain_123"):
            with patch("bot.autonomous.ChainRunner") as mock_runner:
                mock_runner_instance = mock_runner.return_value
                mock_runner_instance.run.return_value = {
                    "status": "complete",
                    "title": "Test Draft"
                }
                with patch("bot.autonomous._notify", new_callable=AsyncMock) as mock_notify:
                    import asyncio
                    asyncio.run(run_scheduled_template("blog_scaffold", mock_send))
                    assert mock_notify.called, "_notify should have been called for blog draft"
                    call_args = mock_notify.call_args[0][0]
                    assert "Blog draft ready" in call_args, f"Expected 'Blog draft ready' in message, got: {call_args}"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
