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


@test("gmail: get_unread_count returns int")
def test_unread_count():
    from tools.api.gmail_api import get_unread_count
    result = get_unread_count()
    assert isinstance(result, int) and result >= 0, \
        f"Expected non-negative int, got {result!r}"


@test("gmail: get_recent_unread returns list")
def test_recent_unread():
    from tools.api.gmail_api import get_recent_unread
    result = get_recent_unread(max_results=3)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


@test("gmail: search_messages returns list")
def test_search_messages():
    from tools.api.gmail_api import search_messages
    result = search_messages("in:inbox", max_results=3)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


@test("gmail: get_messages_from with sender returns list")
def test_messages_from():
    from tools.api.gmail_api import get_messages_from
    result = get_messages_from("noreply@github.com", max_results=3, unread_only=False)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


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


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
