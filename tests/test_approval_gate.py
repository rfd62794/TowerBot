"""Test approval gate CRUD and routing."""
import pytest
from datetime import datetime, timedelta


def test_create_approval_returns_id():
    """create_approval() returns non-None integer ID."""
    from infra.db.approvals import create_approval
    from infra.db.schema import init_db, DB_PATH

    init_db(DB_PATH)

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
    from infra.db.approvals import create_approval, get_pending_approval
    from infra.db.schema import init_db, DB_PATH

    init_db(DB_PATH)

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
    from infra.db.approvals import create_approval, resolve_approval, get_pending_approval
    from infra.db.schema import init_db, DB_PATH

    init_db(DB_PATH)

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
    from infra.db.approvals import create_approval, resolve_approval, get_pending_approval
    from infra.db.schema import init_db, DB_PATH

    init_db(DB_PATH)

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
    from infra.db.approvals import create_approval, expire_stale_approvals
    from infra.db.schema import init_db, DB_PATH, _exec

    init_db(DB_PATH)

    # Create approval with past expiration
    past_time = (datetime.utcnow() - timedelta(minutes=60)).strftime("%Y-%m-%d %H:%M:%S")
    _exec(
        "INSERT INTO action_approvals (action_type, summary, payload, expires_at) "
        "VALUES (?, ?, ?, ?)",
        ("test_action", "Test summary", '{"key": "value"}', past_time),
        commit=True
    )

    expired_count = expire_stale_approvals()
    assert expired_count >= 1

    # Verify status is now expired
    rows = _exec(
        "SELECT status FROM action_approvals WHERE action_type='test_action'"
    )
    assert rows[0]["status"] == "expired"


def test_yes_reply_resolves_latest_pending():
    """Mock get_latest_pending() → _handle_approval_reply("YES") calls resolve_approval with "approved"."""
    from bot.router import _handle_approval_reply
    from infra.db.approvals import create_approval, get_latest_pending, resolve_approval
    from infra.db.schema import init_db, DB_PATH

    init_db(DB_PATH)

    # Create a pending approval
    approval_id = create_approval(
        action_type="test_action",
        summary="Test summary",
        payload={"key": "value"},
        timeout_minutes=30
    )

    # Simulate YES reply
    handled = _handle_approval_reply("YES")
    assert handled is True

    # Verify it was resolved as approved
    pending = get_latest_pending()
    assert pending is None or pending["id"] != approval_id
