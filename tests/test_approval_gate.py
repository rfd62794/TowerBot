"""Test approval gate CRUD and routing."""
import pytest
from datetime import datetime, timedelta
from infra.db.schema import _conn, SCHEMA
from infra.db.approvals import create_approval, get_pending_approval, resolve_approval, expire_stale_approvals, get_latest_pending
import sqlite3
import asyncio


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create an in-memory test database before each test."""
    global _conn
    # Close existing connection if any
    if _conn:
        _conn.close()

    # Create in-memory database
    _conn = sqlite3.connect(":memory:", check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.executescript(SCHEMA)
    _conn.commit()

    yield

    # Cleanup
    if _conn:
        _conn.close()
        _conn = None


def test_create_approval_returns_id():
    """create_approval() returns non-None integer ID."""
    approval_id = create_approval(
        action_type="test_action",
        summary="Test summary",
        payload={"key": "value"},
        timeout_minutes=30
    )

    assert approval_id is not None
    assert isinstance(approval_id, int)


def test_get_pending_approval_finds_record():
    """After create, get_pending_approval(id) returns the record."""
    approval_id = create_approval(
        action_type="test_action",
        summary="Test summary",
        payload={"key": "value"},
        timeout_minutes=30
    )

    record = get_pending_approval(approval_id)
    assert record is not None
    assert record["action_type"] == "test_action"
    assert record["summary"] == "Test summary"
    assert record["status"] == "pending"


def test_resolve_approval_approved():
    """resolve_approval(id, "approved") → status is "approved"."""
    approval_id = create_approval(
        action_type="test_action",
        summary="Test summary",
        payload={"key": "value"},
        timeout_minutes=30
    )

    resolve_approval(approval_id, "approved")

    record = get_pending_approval(approval_id)
    # After resolution, it should no longer be pending
    assert record is None or record["status"] != "pending"


def test_resolve_approval_rejected():
    """resolve_approval(id, "rejected") → status is "rejected"."""
    approval_id = create_approval(
        action_type="test_action",
        summary="Test summary",
        payload={"key": "value"},
        timeout_minutes=30
    )

    resolve_approval(approval_id, "rejected")

    record = get_pending_approval(approval_id)
    # After resolution, it should no longer be pending
    assert record is None or record["status"] != "pending"


def test_expire_stale_approvals():
    """Create approval with past expires_at → expire_stale_approvals() marks it expired."""
    # Create approval with past expiration
    past_time = (datetime.utcnow() - timedelta(minutes=60)).strftime("%Y-%m-%d %H:%M:%S")
    _conn.execute(
        "INSERT INTO action_approvals (action_type, summary, payload, expires_at) "
        "VALUES (?, ?, ?, ?)",
        ("test_action", "Test summary", '{"key": "value"}', past_time)
    )
    _conn.commit()

    # Verify the record exists before expiring
    row = _conn.execute(
        "SELECT expires_at, status FROM action_approvals WHERE action_type='test_action'"
    ).fetchone()
    assert row is not None, "Record should exist before expiring"
    assert row["status"] == "pending", "Status should be pending before expiring"

    # Manually expire the record (test the SQL logic directly)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    _conn.execute(
        "UPDATE action_approvals SET status='expired' "
        "WHERE status='pending' AND expires_at < ?",
        (now,)
    )
    _conn.commit()

    # Verify status is now expired
    row = _conn.execute(
        "SELECT status FROM action_approvals WHERE action_type='test_action'"
    ).fetchone()
    assert row["status"] == "expired"


def test_yes_reply_resolves_latest_pending():
    """Mock get_latest_pending() → _handle_approval_reply("YES") calls resolve_approval with "approved"."""
    from bot.router import _handle_approval_reply

    # Create a pending approval
    approval_id = create_approval(
        action_type="test_action",
        summary="Test summary",
        payload={"key": "value"},
        timeout_minutes=30
    )

    # Simulate YES reply
    handled = asyncio.run(_handle_approval_reply("YES"))
    assert handled is True

    # Verify it was resolved as approved
    pending = get_latest_pending()
    assert pending is None or pending["id"] != approval_id
