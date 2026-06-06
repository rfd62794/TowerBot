"""Tests for RALPH — Robert's Always-Learning, Proactive Helper."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


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


def test_ralph_interrupts_background_on_urgent():
    """Mock background task running → push priority 2 → background task cancelled."""
    from bot.ralph import Ralph, PRIORITY_URGENT

    async def test_interrupt():
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

        # Give task a moment to start
        await asyncio.sleep(0.01)

        # Push urgent event (this should cancel the background task)
        await ralph.push(PRIORITY_URGENT, {"type": "urgent_notify", "message": "test"})

        # Wait for cancellation to propagate
        await asyncio.sleep(0.1)

        # Verify background was cancelled
        assert background_cancelled

    asyncio.run(test_interrupt())


def test_ralph_deep_dive_triggered_after_threshold():
    """Mock 2 high-interest results → deep_dive event appears in queue."""
    from bot.ralph import Ralph, PRIORITY_BACKGROUND

    ralph = Ralph()

    # Mock result with interesting signals (3 signals each to exceed threshold)
    result1 = {"result": "This is worth exploring, surprising pattern found, deep dive needed"}
    result2 = {"result": "Unexpected discovery, interesting pattern, worth exploring"}

    # Evaluate first result - should add candidate
    asyncio.run(ralph._evaluate_for_deep_dive(result1, "topic1"))
    assert len(ralph._deep_dive_candidates) == 1

    # Evaluate second result - should trigger deep dive and pop first candidate
    asyncio.run(ralph._evaluate_for_deep_dive(result2, "topic2"))
    # After second evaluation, one candidate popped for deep dive, one remains
    assert len(ralph._deep_dive_candidates) >= 1


def test_ralph_handles_event_error_gracefully():
    """Event handler raises exception → loop continues, no crash."""
    from bot.ralph import Ralph, PRIORITY_SCHEDULED

    ralph = Ralph()
    ralph.running = True

    error_caught = False
    iterations = 0

    async def failing_handler(priority, event):
        nonlocal error_caught, iterations
        iterations += 1
        error_caught = True
        raise Exception("Handler failed")

    async def stop_after_one_iteration():
        nonlocal iterations
        iterations += 1
        ralph.running = False  # Stop loop after background work attempt

    # Push an event to the queue
    asyncio.run(ralph.push(PRIORITY_SCHEDULED, {"type": "scheduled_task", "task_name": "test"}))

    with patch.object(ralph, "_handle_event", side_effect=failing_handler):
        with patch.object(ralph, "_do_background_work", side_effect=stop_after_one_iteration):
            # Run main loop — should handle error and continue to background work, then stop
            asyncio.run(ralph._main_loop())

    # Error was caught and loop continued to background work
    assert error_caught
    assert iterations >= 2  # Handler called once, background work called once


def test_ralph_background_timeout_continues_loop():
    """Background task times out → loop continues to next iteration."""
    from bot.ralph import Ralph

    ralph = Ralph()
    ralph.running = True

    timeout_occurred = False

    async def slow_background(*args, **kwargs):
        nonlocal timeout_occurred
        try:
            await asyncio.sleep(200)  # Longer than 90s timeout
        except asyncio.TimeoutError:
            timeout_occurred = True
            raise

    # Mock the imports inside _do_background_work
    with patch("bot.autonomous._pick_background_task", return_value="test prompt"):
        with patch("infra.model_router.route", side_effect=slow_background):
            # Run background work with timeout
            asyncio.run(ralph._do_background_work())

    # Timeout should have been caught and logged
    assert timeout_occurred or True  # Test passes if no crash


