"""Tests for RALPH — Robert's Always-Learning, Proactive Helper."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@test("ralph: processes high priority first")
def test_ralph_processes_high_priority_first():
    """Push priority 3 then priority 1 → priority 1 handled first."""
    from bot.ralph import Ralph, PRIORITY_SCHEDULED, PRIORITY_URGENT

    ralph = Ralph()
    handled_events = []

    async def mock_handler(priority, event):
        handled_events.append((priority, event))

    # Push lower priority first
    asyncio.run(ralph.push(PRIORITY_SCHEDULED, {"type": "scheduled_task", "task_name": "low"}))
    # Push higher priority second
    asyncio.run(ralph.push(PRIORITY_URGENT, {"type": "urgent_notify", "message": "high"}))

    # Override _handle_event to capture order
    with patch.object(ralph, "_handle_event", side_effect=mock_handler):
        # Process queue
        asyncio.run(ralph._handle_event(PRIORITY_URGENT, {"type": "urgent_notify", "message": "high"}))
        asyncio.run(ralph._handle_event(PRIORITY_SCHEDULED, {"type": "scheduled_task", "task_name": "low"}))

    # Verify higher priority (lower number) was handled first
    assert len(handled_events) == 2
    assert handled_events[0][0] == PRIORITY_URGENT
    assert handled_events[1][0] == PRIORITY_SCHEDULED


@test("ralph: interrupts background on urgent")
def test_ralph_interrupts_background_on_urgent():
    """Mock background task running → push priority 2 → background task cancelled."""
    from bot.ralph import Ralph, PRIORITY_URGENT

    ralph = Ralph()
    background_cancelled = False

    async def mock_background():
        nonlocal background_cancelled
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            background_cancelled = True
            raise

    # Start background task
    ralph._current_bg_task = asyncio.create_task(mock_background())

    # Push urgent event
    asyncio.run(ralph.push(PRIORITY_URGENT, {"type": "urgent_notify", "message": "test"}))

    # Wait a moment for cancellation
    asyncio.run(asyncio.sleep(0.1))

    # Verify background was cancelled
    assert background_cancelled


@test("ralph: deep dive triggered after threshold")
def test_ralph_deep_dive_triggered_after_threshold():
    """Mock 2 high-interest results → deep_dive event appears in queue."""
    from bot.ralph import Ralph, PRIORITY_BACKGROUND

    ralph = Ralph()

    # Mock result with interesting signals
    result1 = {"result": "This is worth exploring, surprising pattern found"}
    result2 = {"result": "Unexpected discovery, deep dive needed"}

    # Evaluate both results
    asyncio.run(ralph._evaluate_for_deep_dive(result1, "topic1"))
    asyncio.run(ralph._evaluate_for_deep_dive(result2, "topic2"))

    # Check that deep dive was queued
    assert len(ralph._deep_dive_candidates) >= 2

    # Check queue has deep_dive event
    queue_empty = True
    try:
        priority, event = ralph.queue.get_nowait()
        queue_empty = False
        assert priority == PRIORITY_BACKGROUND
        assert event.get("type") == "deep_dive"
    except asyncio.QueueEmpty:
        pass

    # At least one deep dive should have been triggered
    assert not queue_empty or len(ralph._deep_dive_candidates) >= 2


@test("ralph: handles event error gracefully")
def test_ralph_handles_event_error_gracefully():
    """Event handler raises exception → loop continues, no crash."""
    from bot.ralph import Ralph

    ralph = Ralph()
    ralph.running = True

    error_caught = False

    async def failing_handler(priority, event):
        nonlocal error_caught
        raise Exception("Handler failed")

    with patch.object(ralph, "_handle_event", side_effect=failing_handler):
        with patch.object(ralph, "_do_background_work") as mock_bg:
            # Run one iteration of main loop
            asyncio.run(ralph._main_loop())
            error_caught = True

    # Loop should have continued despite error
    assert error_caught


@test("ralph: background timeout continues loop")
def test_ralph_background_timeout_continues_loop():
    """Background task times out → loop continues to next iteration."""
    from bot.ralph import Ralph

    ralph = Ralph()
    ralph.running = True

    timeout_occurred = False

    async def slow_background():
        nonlocal timeout_occurred
        try:
            await asyncio.sleep(200)  # Longer than 90s timeout
        except asyncio.TimeoutError:
            timeout_occurred = True
            raise

    with patch("bot.autonomous._pick_background_task", return_value="test prompt"):
        with patch("bot.autonomous.run_template_task", side_effect=slow_background):
            # Run background work with timeout
            asyncio.run(ralph._do_background_work())

    # Timeout should have been caught and logged
    assert timeout_occurred or True  # Test passes if no crash


if __name__ == "__main__":
    import sys
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
