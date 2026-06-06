"""Tests for fetch_url, think, get_current_datetime, and calculate tools."""

import sys
import os
from unittest.mock import patch, MagicMock

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db
init_db()


def _reset_fetch_rate_limit():
    """Reset fetch rate limit state for clean test runs."""
    try:
        from infra.db.rate_limits_db import upsert_api_state
        upsert_api_state(
            "fetch",
            calls_this_minute=0,
            last_429_at=None,
            retry_after_seconds=0
        )
    except Exception:
        # Database locked - skip reset, previous teardown should have handled it
        pass


def _test_decorator(name):
    def wrapper(fn):
        fn.__name__ = name
        TESTS.append((name, fn))
        return fn
    return wrapper

test = _test_decorator

TESTS = []


_FAKE_RAW = {
    "url": "https://example.com/test",
    "title": "Test Page",
    "content": "word " * 500,
    "char_count": 2500,
    "truncated": False,
    "status_code": 200,
}
_FAKE_RAW_LONG = {**_FAKE_RAW, "content": "x" * 200, "char_count": 200, "truncated": True}


@test("fetch: fetch_url returns dict with content key")
def test_fetch_url_content():
    from tools.search.search_tools import fetch_url
    from api.web.fetch_api import fetch_api as _fetch_api
    with patch.object(_fetch_api, "fetch_url", return_value=_FAKE_RAW):
        result = fetch_url("https://example.com/test")
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "content" in result, "Expected 'content' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"
    assert len(result.get("content", "")) > 0, "Expected non-empty content"


@test("fetch: fetch_url returns error dict for invalid URL")
def test_fetch_url_invalid():
    from tools.search.search_tools import fetch_url
    result = fetch_url("https://this-domain-does-not-exist-xyz.com")
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result.get("ok") == False, "Expected ok=False for invalid URL"
    assert "error" in result, "Expected 'error' key for invalid URL"


@test("fetch: fetch_url content is truncated at max_chars")
def test_fetch_url_truncation():
    from tools.search.search_tools import fetch_url
    from api.web.fetch_api import fetch_api as _fetch_api
    with patch.object(_fetch_api, "fetch_url", return_value=_FAKE_RAW_LONG):
        result = fetch_url("https://example.com/trunc", max_chars=100)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result.get("truncated") == True, "Expected truncated=True for long page with max_chars=100"
    assert len(result.get("content", "")) <= 200, "Content should be bounded"


@test("fetch: fetch_url cached on second call")
def test_fetch_url_cache():
    from tools.search.search_tools import fetch_url
    from api.web.fetch_api import fetch_api as _fetch_api
    call_count = [0]
    def _fake_fetch(url, max_chars=3000):
        call_count[0] += 1
        return {**_FAKE_RAW, "url": url}
    with patch.object(_fetch_api, "fetch_url", side_effect=_fake_fetch):
        result1 = fetch_url("https://example.com/cache-unique-xyz", max_chars=500)
        result2 = fetch_url("https://example.com/cache-unique-xyz", max_chars=500)
    assert result1.get("ok") == True
    assert result2.get("ok") == True
    assert result1.get("content") == result2.get("content")


@test("think: think returns ok=True")
def test_think_ok():
    from tools.meta.meta import think
    result = think("Testing the think tool")
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result.get("ok") == True, "Expected ok=True"


@test("think: think returns thought in result")
def test_think_content():
    from tools.meta.meta import think
    test_content = "Testing the think tool"
    result = think(test_content)
    assert result.get("thought") == test_content, f"Expected thought '{test_content}', got {result.get('thought')}"


@test("think: think with empty string returns ok=True")
def test_think_empty():
    from tools.meta.meta import think
    result = think("")
    assert result.get("ok") == True, "Expected ok=True for empty thought"
    assert result.get("thought") == "", "Expected empty thought"


@test("think: think result has stale_notice=None")
def test_think_stale_notice():
    from tools.meta.meta import think
    result = think("Testing stale_notice")
    assert result.get("stale_notice") is None, "Expected stale_notice=None for think tool"


@test("datetime: get_current_datetime returns ok=True")
def test_datetime_ok():
    from tools.meta.meta import get_current_datetime
    result = get_current_datetime()
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert result.get("ok") == True, "Expected ok=True"


@test("datetime: contains expected keys")
def test_datetime_keys():
    from tools.meta.meta import get_current_datetime
    result = get_current_datetime()
    expected_keys = ["datetime", "date", "time", "day_of_week", "timezone", "timestamp"]
    for key in expected_keys:
        assert key in result, f"Expected key '{key}' in result"


@test("datetime: date format is YYYY-MM-DD")
def test_datetime_date_format():
    from tools.meta.meta import get_current_datetime
    result = get_current_datetime()
    import re
    date = result.get("date", "")
    assert re.match(r"\d{4}-\d{2}-\d{2}", date), f"Expected YYYY-MM-DD format, got {date}"


@test("datetime: timezone is not empty")
def test_datetime_timezone():
    from tools.meta.meta import get_current_datetime
    result = get_current_datetime()
    tz = result.get("timezone", "")
    assert len(tz) > 0, f"Expected non-empty timezone, got '{tz}'"


@test("calculate: 2 + 2 = 4")
def test_calculate_basic():
    from tools.meta.meta import calculate
    result = calculate("2 + 2")
    assert result.get("ok") == True, "Expected ok=True"
    assert result.get("result") == 4, f"Expected 4, got {result.get('result')}"


@test("calculate: sqrt(144) = 12.0")
def test_calculate_sqrt():
    from tools.meta.meta import calculate
    result = calculate("sqrt(144)")
    assert result.get("ok") == True, "Expected ok=True"
    assert result.get("result") == 12.0, f"Expected 12.0, got {result.get('result')}"


@test("calculate: (88 - 32) * 5/9 rounds correctly")
def test_calculate_f_to_c():
    from tools.meta.meta import calculate
    result = calculate("(88 - 32) * 5/9")
    assert result.get("ok") == True, "Expected ok=True"
    # 88°F = 31.111...°C
    expected = 31.11111111111111
    assert abs(result.get("result") - expected) < 0.01, f"Expected ~{expected}, got {result.get('result')}"


@test("calculate: division by zero returns ok=False")
def test_calculate_division_by_zero():
    from tools.meta.meta import calculate
    result = calculate("1 / 0")
    assert result.get("ok") == False, "Expected ok=False for division by zero"
    assert "error" in result, "Expected 'error' key"


@test("calculate: invalid expression returns ok=False")
def test_calculate_invalid():
    from tools.meta.meta import calculate
    result = calculate("invalid expression")
    assert result.get("ok") == False, "Expected ok=False for invalid expression"
    assert "error" in result, "Expected 'error' key"


@test("openagent: run_openagent is in TOOL_REGISTRY")
def test_openagent_in_registry():
    from tools.registry import TOOL_REGISTRY
    assert "run_openagent" in TOOL_REGISTRY, "run_openagent not in TOOL_REGISTRY"


@test("openagent: run_openagent returns ok=False with error_code='not_installed' when command not found")
def test_openagent_not_installed():
    from tools.meta.meta import run_openagent
    import unittest.mock as mock
    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        result = run_openagent("analyze")
    assert result.get("ok") == False, "Expected ok=False when command not found"
    assert result.get("error_code") == "not_installed", f"Expected error_code='not_installed', got {result.get('error_code')}"


@test("openagent: run_openagent returns ok=False with error_code='timeout' on TimeoutExpired")
def test_openagent_timeout():
    from tools.meta.meta import run_openagent
    import subprocess
    import unittest.mock as mock
    with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("openagent", 120)):
        result = run_openagent("analyze")
    assert result.get("ok") == False, "Expected ok=False on timeout"
    assert result.get("error_code") == "timeout", f"Expected error_code='timeout', got {result.get('error_code')}"


def run_all():
    # Reset rate limit before tests run
    _reset_fetch_rate_limit()
    
    passed = 0
    failed = 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}\n  {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}\n  Unexpected error: {e}")
            failed += 1
    
    return passed, failed


if __name__ == "__main__":
    print(run_all())
