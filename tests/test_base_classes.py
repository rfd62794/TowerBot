"""Tests for tools/api/_handler.py (BaseAPIHandler) and tools/_tool.py (BaseTool)."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from core.db import init_db
init_db()

from tools.api._handler import BaseAPIHandler
from tools._tool import BaseTool

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


# ─── BaseAPIHandler tests ────────────────────────


class MockAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "mock"

    def _get_client(self):
        return {"client": "mock"}


class BadHandler(BaseAPIHandler):
    CACHE_PREFIX = ""

    def _get_client(self):
        return {"client": "bad"}


@test("handler: cache_key returns namespaced key")
def test_handler_cache_key():
    handler = MockAPIHandler()
    key = handler.cache_key("current")
    assert key == "mock_current", f"Expected 'mock_current', got '{key}'"


@test("handler: cache_key raises if CACHE_PREFIX not set")
def test_handler_cache_key_no_prefix():
    handler = BadHandler()
    try:
        handler.cache_key("test")
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError as e:
        assert "must set CACHE_PREFIX" in str(e)


@test("handler: hash delegates to cache.hash()")
def test_handler_hash():
    handler = MockAPIHandler()
    h1 = handler.hash("test")
    h2 = handler.hash("test")
    assert h1 == h2, "Hash should be consistent"
    assert isinstance(h1, str), "Hash should be string"


@test("handler: call delegates to cache.call()")
def test_handler_call():
    handler = MockAPIHandler()

    def live_fn():
        return {"value": 42}

    result = handler.call("test", handler.hash(), live_fn)
    assert result["value"] == 42, "Expected live data"
    # Clean up
    from core.cache import cache
    cache.invalidate("mock_test", handler.hash())


@test("handler: call with stale_ok=False")
def test_handler_call_stale_not_ok():
    handler = MockAPIHandler()

    def live_fn():
        return {"value": 99}

    result = handler.call("test2", handler.hash(), live_fn, stale_ok=False)
    assert result["value"] == 99, "Expected live data"
    # Clean up
    from core.cache import cache
    cache.invalidate("mock_test2", handler.hash())


# ─── BaseTool tests ──────────────────────────────


class MockTool(BaseTool):
    pass


@test("tool: success() returns ok=True with data")
def test_tool_success():
    tool = MockTool()
    result = tool.success({"temp_f": 72, "condition": "Clear"})
    assert result["ok"] is True, "Expected ok=True"
    assert result["temp_f"] == 72, "Expected temp_f=72"
    assert result["condition"] == "Clear", "Expected condition=Clear"
    assert result["stale_notice"] is None, "Expected stale_notice=None"


@test("tool: success() strips internal keys from data")
def test_tool_success_strips_internal():
    tool = MockTool()
    result = tool.success({"temp_f": 72, "_stale": True, "_cached_at": "2026-05-30"})
    assert result["ok"] is True, "Expected ok=True"
    assert result["temp_f"] == 72, "Expected temp_f=72"
    assert "_stale" not in result, "Expected _stale stripped"
    assert "_cached_at" not in result, "Expected _cached_at stripped"


@test("tool: success() with stale_result extracts stale_notice")
def test_tool_success_with_stale():
    tool = MockTool()
    stale_result = {"_stale": True, "_age_minutes": 90, "_cached_at": "2026-05-30 07:00:00"}
    result = tool.success({"temp_f": 70}, stale_result=stale_result)
    assert result["ok"] is True, "Expected ok=True"
    assert result["stale_notice"] is not None, "Expected stale_notice"
    assert "ago" in result["stale_notice"], "Expected 'ago' in notice"


@test("tool: error() returns ok=False with error message")
def test_tool_error():
    tool = MockTool()
    result = tool.error("Service unavailable")
    assert result["ok"] is False, "Expected ok=False"
    assert result["error"] == "Service unavailable", "Expected error message"
    assert result["stale_notice"] is None, "Expected stale_notice=None"


@test("tool: error() with code")
def test_tool_error_with_code():
    tool = MockTool()
    result = tool.error("API timeout", code="timeout")
    assert result["ok"] is False, "Expected ok=False"
    assert result["error"] == "API timeout", "Expected error message"
    assert result["error_code"] == "timeout", "Expected error_code"


@test("tool: stale_notice() delegates to cache.stale_notice()")
def test_tool_stale_notice():
    tool = MockTool()
    fresh_result = {"_stale": False}
    notice = tool.stale_notice(fresh_result)
    assert notice is None, "Expected None for fresh result"

    stale_result = {"_stale": True, "_age_minutes": 45, "_cached_at": "2026-05-30 08:15:00"}
    notice = tool.stale_notice(stale_result)
    assert notice is not None, "Expected notice for stale result"
    assert "ago" in notice, "Expected 'ago' in notice"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
