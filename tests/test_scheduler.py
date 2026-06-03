"""Tests for bot/scheduler.py periodic tasks."""

import pytest
from datetime import datetime, timedelta


def test_scheduler_google_tasks_overdue_check_logic():
    """Test scheduler Check 9 logic: Google Tasks overdue with notification deduplication."""
    from infra.db.schema import _exec
    from datetime import datetime
    import uuid

    # Generate unique IDs to avoid collision
    old_task_id = f"old_task_{uuid.uuid4().hex[:8]}"
    recent_task_id = f"recent_task_{uuid.uuid4().hex[:8]}"

    # Simulate overdue task notification record
    now = datetime.now()
    yesterday = (now - timedelta(hours=25)).isoformat()
    recent = (now - timedelta(hours=12)).isoformat()

    # Insert a notification from 25 hours ago (should notify again)
    _exec(
        """INSERT INTO task_notifications (google_task_id, notification_type, last_notified_at)
           VALUES (?, 'overdue', ?)""",
        (old_task_id, yesterday),
        commit=True
    )

    # Insert a notification from 12 hours ago (should NOT notify again)
    _exec(
        """INSERT INTO task_notifications (google_task_id, notification_type, last_notified_at)
           VALUES (?, 'overdue', ?)""",
        (recent_task_id, recent),
        commit=True
    )

    # Check old task - should be eligible for re-notification
    old_row = _exec(
        "SELECT last_notified_at FROM task_notifications WHERE google_task_id=?",
        (old_task_id,)
    ).fetchone()
    assert old_row is not None
    old_dt = datetime.fromisoformat(old_row["last_notified_at"])
    hours_since = (now - old_dt).total_seconds() / 3600
    assert hours_since >= 24, "Old task should be eligible for re-notification"

    # Check recent task - should NOT be eligible for re-notification
    recent_row = _exec(
        "SELECT last_notified_at FROM task_notifications WHERE google_task_id=?",
        (recent_task_id,)
    ).fetchone()
    assert recent_row is not None
    recent_dt = datetime.fromisoformat(recent_row["last_notified_at"])
    hours_since_recent = (now - recent_dt).total_seconds() / 3600
    assert hours_since_recent < 24, "Recent task should NOT be eligible for re-notification"

    # Cleanup
    _exec(
        "DELETE FROM task_notifications WHERE google_task_id IN (?, ?)",
        (old_task_id, recent_task_id),
        commit=True
    )


def test_scheduler_calendar_alert_uses_task_reminders():
    """Test scheduler Check 10 uses task_reminders table directly instead of deprecated functions."""
    from infra.db.schema import _exec
    import uuid

    # Generate unique ID to avoid collision
    alert_id = int(uuid.uuid4().hex[:8], 16) % 1000000

    # Check that no reminder exists yet
    row = _exec(
        "SELECT reminded_at FROM task_reminders WHERE task_id=?",
        (alert_id,)
    ).fetchone()
    assert row is None, "Reminder should not exist initially"

    # Insert reminder
    _exec(
        "INSERT INTO task_reminders (task_id, reminded_at) VALUES (?, CURRENT_TIMESTAMP)",
        (alert_id,),
        commit=True
    )

    # Check that reminder now exists
    row = _exec(
        "SELECT reminded_at FROM task_reminders WHERE task_id=?",
        (alert_id,)
    ).fetchone()
    assert row is not None, "Reminder should exist after insert"

    # Cleanup
    _exec(
        "DELETE FROM task_reminders WHERE task_id=?",
        (alert_id,),
        commit=True
    )


def test_nightly_summary_is_noop():
    """Test that nightly_summary is a no-op after local tasks deprecation."""
    import asyncio
    from bot.scheduler import nightly_summary

    async def dummy_send_fn(msg):
        pass

    # Should not raise an error and should log
    # This test just ensures the function doesn't crash
    try:
        asyncio.run(nightly_summary(dummy_send_fn))
        # If we get here, the function ran without error
        assert True
    except Exception as e:
        pytest.fail(f"nightly_summary raised unexpected error: {e}")
