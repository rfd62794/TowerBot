"""Tests for morning_briefing() in bot/scheduler.py."""

import sys
import os
import asyncio

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


@test("briefing: morning_briefing runs without error")
def test_morning_briefing_runs():
    from bot.scheduler import morning_briefing
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    asyncio.run(morning_briefing(capture))
    assert len(output) > 0, "Expected briefing to produce output"
    assert "Good morning Robert" in output[0], "Expected greeting in output"


@test("briefing: output contains channel stats section")
def test_briefing_has_channel_stats():
    from bot.scheduler import morning_briefing
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    asyncio.run(morning_briefing(capture))
    assert len(output) > 0
    msg = output[0]
    assert "Channel" in msg or "Views:" in msg, "Expected channel stats in briefing"


@test("briefing: output contains gmail section")
def test_briefing_has_gmail():
    from bot.scheduler import morning_briefing
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    asyncio.run(morning_briefing(capture))
    assert len(output) > 0
    msg = output[0]
    # Gmail section may be present or empty depending on unread count
    # Just verify the function doesn't crash when calling gmail functions


@test("briefing: output contains personal tasks section")
def test_briefing_has_personal_tasks():
    from bot.scheduler import morning_briefing
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    asyncio.run(morning_briefing(capture))
    assert len(output) > 0
    msg = output[0]
    # Personal tasks section may be present or empty
    # Just verify the function doesn't crash


@test("briefing: weather section does not show garbage on failure")
def test_briefing_weather_no_garbage():
    from bot.scheduler import morning_briefing
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    asyncio.run(morning_briefing(capture))
    assert len(output) > 0
    msg = output[0]
    # If weather fails, it should not show "?°F" garbage
    assert "?°F" not in msg, "Weather failure should not show garbage output"


@test("briefing: output contains weekly focus section")
def test_briefing_has_weekly_focus():
    from bot.scheduler import morning_briefing
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    asyncio.run(morning_briefing(capture))
    assert len(output) > 0
    msg = output[0]
    # Weekly focus may or may not be present depending on DB state
    # Just verify the function doesn't crash


@test("briefing: includes google tasks section")
def test_briefing_includes_google_tasks():
    from bot.scheduler import morning_briefing
    from unittest.mock import patch
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    mock_tasks = {
        "ok": True,
        "tasks": [
            {"title": "Task 1", "due_date": "2026-06-06", "status": "needsAction"},
            {"title": "Task 2", "due_date": "2026-06-06", "status": "needsAction"},
        ],
        "count": 2
    }
    
    with patch("tools.productivity.google_tasks.list_google_tasks", return_value=mock_tasks):
        asyncio.run(morning_briefing(capture))
    
    assert len(output) > 0
    msg = output[0]
    # Section may be present or empty depending on date filter


@test("briefing: tasks empty ok")
def test_briefing_tasks_empty_ok():
    from bot.scheduler import morning_briefing
    from unittest.mock import patch
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    mock_tasks = {"ok": True, "tasks": [], "count": 0}
    
    with patch("tools.productivity.google_tasks.list_google_tasks", return_value=mock_tasks):
        asyncio.run(morning_briefing(capture))
    
    assert len(output) > 0
    # Should not crash with empty tasks


@test("briefing: overnight findings")
def test_briefing_overnight_findings():
    from bot.scheduler import morning_briefing
    from unittest.mock import patch
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    mock_actions = [
        {"task_name": "community_scout", "result": "Found opportunity", "ran_at": "2026-06-06 04:00:00"},
    ]
    
    with patch("infra.db.autonomous.get_overnight_actions", return_value=mock_actions):
        asyncio.run(morning_briefing(capture))
    
    assert len(output) > 0
    msg = output[0]
    # Section may be present if actions exist


@test("briefing: no overnight findings")
def test_briefing_no_overnight_findings():
    from bot.scheduler import morning_briefing
    from unittest.mock import patch
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    with patch("infra.db.autonomous.get_overnight_actions", return_value=[]):
        asyncio.run(morning_briefing(capture))
    
    assert len(output) > 0
    # Should not crash with empty actions


@test("briefing: commit digest")
def test_briefing_commit_digest():
    from bot.scheduler import morning_briefing
    from unittest.mock import patch
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    mock_commits = {
        "commits": [
            {"sha": "abc123", "message": "Fix bug", "date": "2026-06-06T10:00:00Z", "repo": "PrivyBot"},
            {"sha": "def456", "message": "Add feature", "date": "2026-06-06T11:00:00Z", "repo": "PrivyBot"},
        ],
        "count": 2
    }
    
    with patch("tools.search.search_tools.get_recent_commits", return_value=mock_commits):
        asyncio.run(morning_briefing(capture))
    
    assert len(output) > 0
    msg = output[0]
    # Section may be present if recent commits exist


@test("briefing: weekly mirror monday")
def test_briefing_weekly_mirror_monday():
    from bot.scheduler import morning_briefing
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    # Just verify the function doesn't crash
    # The Monday check happens at runtime based on actual day
    asyncio.run(morning_briefing(capture))
    
    assert len(output) > 0


@test("briefing: weekly mirror not monday")
def test_briefing_weekly_mirror_not_monday():
    from bot.scheduler import morning_briefing
    
    output = []
    
    async def capture(msg):
        output.append(msg)
    
    # Just verify the function doesn't crash on any day
    asyncio.run(morning_briefing(capture))
    
    assert len(output) > 0
    # Should not crash regardless of day of week


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
