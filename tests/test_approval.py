"""Tests for approval flow — Phase 20b.

All tests use isolated in-memory SQLite. No real Telegram calls.
"""
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import pytest
from infra.db.schema import init_db


@pytest.fixture()
def test_db():
    from infra.db import schema
    schema.init_db(":memory:")
    yield schema._conn
    if schema._conn:
        schema._conn.close()
        schema._conn = None


# --- approval.py CRUD tests ---

def test_create_listener(test_db):
    """create_listener() returns dict with status='waiting'."""
    from infra.chain.approval import create_listener
    listener = create_listener("chain-1", "step-1", "chat-123")
    assert listener is not None
    assert listener['status'] == 'waiting'
    assert listener['chain_id'] == 'chain-1'
    assert listener['step_id'] == 'step-1'
    assert listener['telegram_chat_id'] == 'chat-123'


def test_get_listener_returns_none_for_missing(test_db):
    """get_listener('bad') returns None."""
    from infra.chain.approval import get_listener
    assert get_listener('nonexistent-id') is None


def test_resolve_listener_approved(test_db):
    """resolve_listener sets status='resolved', response='approved'."""
    from infra.chain.approval import create_listener, resolve_listener, get_listener
    listener = create_listener("chain-1", "step-1", "chat-123")
    resolve_listener(listener['id'], 'approved', 'msg-456')
    updated = get_listener(listener['id'])
    assert updated['status'] == 'resolved'
    assert updated['response'] == 'approved'
    assert updated['message_id'] == 'msg-456'


def test_resolve_listener_idempotent(test_db):
    """resolve_listener called twice — no error, still resolved."""
    from infra.chain.approval import create_listener, resolve_listener, get_listener
    listener = create_listener("chain-1", "step-1", "chat-123")
    resolve_listener(listener['id'], 'approved')
    resolve_listener(listener['id'], 'approved')  # second call
    updated = get_listener(listener['id'])
    assert updated['status'] == 'resolved'


def test_get_waiting_listener_for_chain(test_db):
    """Returns waiting listener for chain, None after resolved."""
    from infra.chain.approval import create_listener, resolve_listener, get_waiting_listener_for_chain
    listener = create_listener("chain-1", "step-1", "chat-123")
    found = get_waiting_listener_for_chain("chain-1")
    assert found is not None
    assert found['id'] == listener['id']
    resolve_listener(listener['id'], 'approved')
    found_after = get_waiting_listener_for_chain("chain-1")
    assert found_after is None


def test_build_approval_message_structure(test_db):
    """Returns dict with text, reply_markup, parse_mode."""
    from infra.chain.approval import build_approval_message
    msg = build_approval_message("chain-1", "step_a", "summary text", "listener-1")
    assert 'text' in msg
    assert 'reply_markup' in msg
    assert msg['parse_mode'] == 'HTML'
    assert 'inline_keyboard' in msg['reply_markup']


def test_build_approval_message_callback_format(test_db):
    """callback_data matches 'approval:{action}:{listener_id}'."""
    from infra.chain.approval import build_approval_message
    msg = build_approval_message("chain-1", "step_a", "summary", "listener-123")
    keyboard = msg['reply_markup']['inline_keyboard']
    approve_btn = keyboard[0][0]
    reject_btn = keyboard[0][1]
    assert approve_btn['callback_data'] == 'approval:approve:listener-123'
    assert reject_btn['callback_data'] == 'approval:reject:listener-123'


# --- steps.py approval_wait handler tests ---

def test_handle_approval_wait_creates_listener(test_db):
    """Creates approval_listeners row, raises StepSkipped."""
    from infra.db.chains import create_chain
    from infra.chain.steps import handle_approval_wait, StepSkipped
    from infra.chain.approval import get_waiting_listener_for_chain
    chain = create_chain("test_template")
    step = {
        'id': 'step-1',
        'chain_id': chain['id'],
        'name': 'approval_step',
        'config': {'telegram_chat_id': 'chat-123'}
    }
    try:
        handle_approval_wait(step, {'x': 1})
        assert False, "Expected StepSkipped"
    except StepSkipped:
        pass
    listener = get_waiting_listener_for_chain(chain['id'])
    assert listener is not None
    assert listener['telegram_chat_id'] == 'chat-123'


def test_handle_approval_wait_missing_chat_id(test_db):
    """Raises StepError when telegram_chat_id missing."""
    from infra.chain.steps import handle_approval_wait, StepError
    step = {'id': 'step-1', 'chain_id': 'c1', 'name': 's1', 'config': {}}
    try:
        handle_approval_wait(step, {})
        assert False, "Expected StepError"
    except StepError:
        pass


def test_handle_approval_wait_calls_send_fn(test_db):
    """Mock send_fn called with message dict and chat_id."""
    from infra.db.chains import create_chain
    from infra.chain.steps import handle_approval_wait, StepSkipped
    from infra.chain.approval import get_waiting_listener_for_chain
    chain = create_chain("test_template")
    step = {
        'id': 'step-1',
        'chain_id': chain['id'],
        'name': 'approval_step',
        'config': {'telegram_chat_id': 'chat-123'}
    }
    calls = []
    def mock_send(msg, chat_id):
        calls.append((msg, chat_id))
    try:
        handle_approval_wait(step, {'x': 1}, send_approval_fn=mock_send)
    except StepSkipped:
        pass
    assert len(calls) == 1
    assert calls[0][1] == 'chat-123'
    assert 'text' in calls[0][0]


def test_handle_approval_wait_no_send_fn(test_db):
    """None send_fn — still creates listener, still raises StepSkipped."""
    from infra.db.chains import create_chain
    from infra.chain.steps import handle_approval_wait, StepSkipped
    from infra.chain.approval import get_waiting_listener_for_chain
    chain = create_chain("test_template")
    step = {
        'id': 'step-1',
        'chain_id': chain['id'],
        'name': 'approval_step',
        'config': {'telegram_chat_id': 'chat-123'}
    }
    try:
        handle_approval_wait(step, {'x': 1}, send_approval_fn=None)
    except StepSkipped:
        pass
    listener = get_waiting_listener_for_chain(chain['id'])
    assert listener is not None


# --- approval_router.py tests ---

def test_is_approval_callback_true(test_db):
    """'approval:approve:abc' returns True."""
    from bot.approval_router import is_approval_callback
    assert is_approval_callback('approval:approve:abc') is True


def test_is_approval_callback_false(test_db):
    """'/start' returns False."""
    from bot.approval_router import is_approval_callback
    assert is_approval_callback('/start') is False


def test_parse_callback_valid(test_db):
    """Returns ('approve', 'listener-id')."""
    from bot.approval_router import parse_callback
    result = parse_callback('approval:approve:listener-123')
    assert result == ('approve', 'listener-123')


def test_parse_callback_invalid(test_db):
    """Malformed string returns None."""
    from bot.approval_router import parse_callback
    assert parse_callback('invalid') is None
    assert parse_callback('approval:approve') is None


def test_handle_callback_approve(test_db):
    """Resolves listener, updates chain to running, returns approved status."""
    from infra.db.chains import create_chain, update_chain_status
    from infra.chain.approval import create_listener
    from bot.approval_router import handle_approval_callback
    chain = create_chain("test_template")
    update_chain_status(chain['id'], 'waiting_approval', current_step=2)
    listener = create_listener(chain['id'], 'step-1', 'chat-123')
    result = handle_approval_callback(
        f'approval:approve:{listener["id"]}',
        resume_chain_fn=None
    )
    assert result['status'] == 'approved'
    assert result['chain_id'] == chain['id']


def test_handle_callback_reject(test_db):
    """Resolves listener, updates chain to failed, returns rejected status."""
    from infra.db.chains import create_chain, update_chain_status
    from infra.chain.approval import create_listener
    from bot.approval_router import handle_approval_callback
    chain = create_chain("test_template")
    update_chain_status(chain['id'], 'waiting_approval')
    listener = create_listener(chain['id'], 'step-1', 'chat-123')
    result = handle_approval_callback(
        f'approval:reject:{listener["id"]}',
        resume_chain_fn=None
    )
    assert result['status'] == 'rejected'
    assert result['chain_id'] == chain['id']


def test_handle_callback_already_resolved(test_db):
    """Second call returns already_resolved status."""
    from infra.db.chains import create_chain
    from infra.chain.approval import create_listener, resolve_listener
    from bot.approval_router import handle_approval_callback
    chain = create_chain("test_template")
    listener = create_listener(chain['id'], 'step-1', 'chat-123')
    resolve_listener(listener['id'], 'approved')
    result = handle_approval_callback(
        f'approval:approve:{listener["id"]}',
        resume_chain_fn=None
    )
    assert result['status'] == 'already_resolved'


# --- run_all shim for verify.py ---

TESTS = [
    ("create_listener", test_create_listener),
    ("get_listener_returns_none_for_missing", test_get_listener_returns_none_for_missing),
    ("resolve_listener_approved", test_resolve_listener_approved),
    ("resolve_listener_idempotent", test_resolve_listener_idempotent),
    ("get_waiting_listener_for_chain", test_get_waiting_listener_for_chain),
    ("build_approval_message_structure", test_build_approval_message_structure),
    ("build_approval_message_callback_format", test_build_approval_message_callback_format),
    ("handle_approval_wait_creates_listener", test_handle_approval_wait_creates_listener),
    ("handle_approval_wait_missing_chat_id", test_handle_approval_wait_missing_chat_id),
    ("handle_approval_wait_calls_send_fn", test_handle_approval_wait_calls_send_fn),
    ("handle_approval_wait_no_send_fn", test_handle_approval_wait_no_send_fn),
    ("is_approval_callback_true", test_is_approval_callback_true),
    ("is_approval_callback_false", test_is_approval_callback_false),
    ("parse_callback_valid", test_parse_callback_valid),
    ("parse_callback_invalid", test_parse_callback_invalid),
    ("handle_callback_approve", test_handle_callback_approve),
    ("handle_callback_reject", test_handle_callback_reject),
    ("handle_callback_already_resolved", test_handle_callback_already_resolved),
]


def run_all() -> tuple[int, int]:
    import infra.db.schema as _schema
    passed = failed = 0
    for name, fn in TESTS:
        _schema.init_db(":memory:")
        conn = _schema._conn
        try:
            fn(conn)
            print(f"  \u2713 approval: {name}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 approval: {name}: {e}")
            failed += 1
        finally:
            if _schema._conn:
                _schema._conn.close()
                _schema._conn = None
    return passed, failed


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
