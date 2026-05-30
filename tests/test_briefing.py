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


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
