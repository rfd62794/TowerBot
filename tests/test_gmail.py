"""Tests for Gmail integration."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from core.db import init_db
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


@test("gmail: credentials load")
def test_credentials():
    from tools.api.gmail_api import _get_gmail_client
    client = _get_gmail_client()
    assert client is not None


@test("gmail: get_unread_count returns dict with count")
def test_unread_count():
    from tools.api.gmail_api import get_unread_count
    result = get_unread_count()
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "count" in result, "Missing 'count' key"
    assert result["count"] >= 0, f"Expected non-negative count, got {result['count']}"


@test("gmail: get_recent_unread returns dict with messages")
def test_recent_unread():
    from tools.api.gmail_api import get_recent_unread
    result = get_recent_unread(max_results=3)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "messages" in result, "Missing 'messages' key"
    assert isinstance(result["messages"], list), f"Expected list for messages, got {type(result['messages'])}"


@test("gmail: search_messages returns dict with messages")
def test_search_messages():
    from tools.api.gmail_api import search_messages
    result = search_messages("in:inbox", max_results=3)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "messages" in result, "Missing 'messages' key"
    assert isinstance(result["messages"], list), f"Expected list for messages, got {type(result['messages'])}"


@test("gmail: get_messages_from returns dict with messages")
def test_messages_from():
    from tools.api.gmail_api import get_messages_from
    result = get_messages_from("noreply@github.com", max_results=3, unread_only=False)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "messages" in result, "Missing 'messages' key"
    assert isinstance(result["messages"], list), f"Expected list for messages, got {type(result['messages'])}"


@test("gmail: get_inbox_summary returns dict with required keys")
def test_inbox_summary():
    from tools.gmail import get_inbox_summary
    result = get_inbox_summary()
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "unread_count" in result, "Missing 'unread_count'"
    assert "has_unread" in result, "Missing 'has_unread'"
    assert "recent" in result, "Missing 'recent'"
    assert isinstance(result["unread_count"], int)
    assert isinstance(result["has_unread"], bool)


@test("gmail: search_email returns dict with count")
def test_search_email():
    from tools.gmail import search_email
    result = search_email("in:inbox", max_results=3)
    assert isinstance(result, dict)
    assert "count" in result
    assert "query" in result
    assert isinstance(result["count"], int)


@test("gmail: check_sender returns has_messages bool")
def test_check_sender():
    from tools.gmail import check_sender
    result = check_sender("noreply@github.com", unread_only=False)
    assert isinstance(result, dict)
    assert "has_messages" in result
    assert isinstance(result["has_messages"], bool)
    assert "sender" in result
    assert "count" in result


@test("gmail: rfd credentials return None gracefully when token missing")
def test_rfd_no_token():
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, {"RFD_GMAIL_TOKEN_PATH": "config/nonexistent_rfd_token.json"}):
        from tools.api.gmail_api import _get_rfd_credentials
        result = _get_rfd_credentials()
        assert result is None, \
            f"Expected None for missing token file, got {result!r}"


@test("gmail: get_all_inbox_summary returns dict with personal and professional keys")
def test_all_inbox_summary_shape():
    from tools.gmail import get_all_inbox_summary
    result = get_all_inbox_summary()
    assert isinstance(result, dict)
    assert "personal" in result, "Missing 'personal' key"
    assert "professional" in result, "Missing 'professional' key"
    assert "total_unread" in result, "Missing 'total_unread' key"
    assert isinstance(result["total_unread"], int)
    assert "unread_count" in result["personal"]
    assert "unread_count" in result["professional"]


@test("gmail: get_all_inbox_summary handles missing RFD token without exception")
def test_all_inbox_summary_no_rfd():
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, {"RFD_GMAIL_TOKEN_PATH": "config/nonexistent_rfd_token.json"}):
        from tools.gmail import get_all_inbox_summary
        # Should not raise exception
        result = get_all_inbox_summary()
        assert isinstance(result, dict)


@test("gmail: check_sender_all returns count and has_messages keys")
def test_check_sender_all():
    from tools.gmail import check_sender_all
    result = check_sender_all("noreply@github.com", unread_only=False)
    assert isinstance(result, dict)
    assert "count" in result
    assert "has_messages" in result
    assert "sender" in result
    assert "messages" in result
    assert isinstance(result["has_messages"], bool)
    assert isinstance(result["messages"], list)


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
