"""Tests for offline-first cache infrastructure (Phase 1)."""

import sys
import os
import datetime

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from core.db import init_db
from core.db.schema import _exec
init_db()

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


@test("offline: get_stale_cached_result returns None when no record exists")
def test_stale_none():
    from core.db import get_stale_cached_result
    result = get_stale_cached_result("test_tool_never_cached", "test_hash")
    assert result is None, f"Expected None for non-existent cache, got {result}"


@test("offline: get_stale_cached_result returns stale record after TTL expiry")
def test_stale_expired():
    from core.db import get_stale_cached_result
    import json

    # Insert a record with expires_at in the past
    past = (datetime.datetime.now() - datetime.timedelta(hours=2)).isoformat()
    _exec(
        "INSERT OR REPLACE INTO tool_cache (tool_name, params_hash, result, fetched_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("test_stale_tool", "test_stale_hash", json.dumps({"data": "stale"}), past, past),
        commit=True,
    )

    result = get_stale_cached_result("test_stale_tool", "test_stale_hash")
    assert result is not None, "Expected stale result to be returned"
    assert result.get("data") == "stale"
    assert result.get("_stale") == True

    # Cleanup
    _exec("DELETE FROM tool_cache WHERE tool_name = ?", ("test_stale_tool",), commit=True)


@test("offline: get_stale_cached_result adds correct metadata fields")
def test_stale_metadata():
    from core.db import get_stale_cached_result
    import json

    past = (datetime.datetime.now() - datetime.timedelta(minutes=30)).isoformat()
    _exec(
        "INSERT OR REPLACE INTO tool_cache (tool_name, params_hash, result, fetched_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("test_meta_tool", "test_meta_hash", json.dumps({"value": 42}), past, past),
        commit=True,
    )

    result = get_stale_cached_result("test_meta_tool", "test_meta_hash")
    assert "_stale" in result
    assert "_cached_at" in result
    assert "_age_minutes" in result
    assert result["_stale"] == True
    assert isinstance(result["_age_minutes"], int)
    assert result["_age_minutes"] >= 28  # Should be ~30 minutes

    # Cleanup
    _exec("DELETE FROM tool_cache WHERE tool_name = ?", ("test_meta_tool",), commit=True)


@test("offline: preload_log table exists in schema")
def test_preload_table_exists():
    from core.db.schema import _exec
    row = _exec(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='preload_log'"
    ).fetchone()
    assert row is not None, "preload_log table missing"


@test("offline: record_preload_result writes to preload_log on success=True")
def test_preload_success():
    from core.db import record_preload_result
    import json

    record_preload_result(
        "test_preload_tool", "test_hash", {"data": "fresh"}, 1.0, True, 100
    )

    row = _exec(
        "SELECT * FROM preload_log WHERE tool_name = ? AND params_hash = ?",
        ("test_preload_tool", "test_hash"),
    ).fetchone()
    assert row is not None
    assert row["success"] == 1
    assert row["duration_ms"] == 100

    # Cleanup
    _exec("DELETE FROM preload_log WHERE tool_name = ?", ("test_preload_tool",), commit=True)
    _exec("DELETE FROM tool_cache WHERE tool_name = ?", ("test_preload_tool",), commit=True)


@test("offline: record_preload_result writes to preload_log on success=False without cache")
def test_preload_failure():
    from core.db import record_preload_result

    record_preload_result(
        "test_fail_tool", "test_hash", {}, 1.0, False, 50, "test error"
    )

    # Should have preload_log entry
    row = _exec(
        "SELECT * FROM preload_log WHERE tool_name = ? AND params_hash = ?",
        ("test_fail_tool", "test_hash"),
    ).fetchone()
    assert row is not None
    assert row["success"] == 0
    assert row["error_msg"] == "test error"

    # Should NOT have cache entry
    cache_row = _exec(
        "SELECT * FROM tool_cache WHERE tool_name = ? AND params_hash = ?",
        ("test_fail_tool", "test_hash"),
    ).fetchone()
    assert cache_row is None

    # Cleanup
    _exec("DELETE FROM preload_log WHERE tool_name = ?", ("test_fail_tool",), commit=True)


@test("offline: get_preload_status returns list")
def test_preload_status_list():
    from core.db import get_preload_status
    result = get_preload_status()
    assert isinstance(result, list)


@test("offline: get_preload_status returns correct age_minutes")
def test_preload_status_age():
    from core.db import record_preload_result, get_preload_status

    record_preload_result(
        "test_age_tool", "test_age_hash", {"data": "test"}, 1.0, True, 10
    )

    status = get_preload_status()
    entry = next((s for s in status if s["tool_name"] == "test_age_tool"), None)
    assert entry is not None
    assert "age_minutes" in entry
    assert isinstance(entry["age_minutes"], int)
    assert entry["age_minutes"] >= 0

    # Cleanup
    _exec("DELETE FROM preload_log WHERE tool_name = ?", ("test_age_tool",), commit=True)
    _exec("DELETE FROM tool_cache WHERE tool_name = ?", ("test_age_tool",), commit=True)


@test("offline: cached_api_call returns fresh data on successful live call")
def test_cached_fresh():
    from tools.api._base import cached_api_call

    def live_fn():
        return {"fresh": True, "value": 123}

    result = cached_api_call("test_fresh_tool", "test_fresh_hash", live_fn, 60)
    assert result.get("fresh") == True
    assert result.get("value") == 123
    assert result.get("_stale") == False

    # Cleanup
    _exec("DELETE FROM tool_cache WHERE tool_name = ?", ("test_fresh_tool",), commit=True)


@test("offline: cached_api_call returns from cache on second call")
def test_cached_hit():
    from tools.api._base import cached_api_call

    call_count = [0]

    def live_fn():
        call_count[0] += 1
        return {"count": call_count[0]}

    # First call — live
    result1 = cached_api_call("test_hit_tool", "test_hit_hash", live_fn, 60)
    assert result1.get("count") == 1

    # Second call — should hit cache, no live call
    result2 = cached_api_call("test_hit_tool", "test_hit_hash", live_fn, 60)
    assert result2.get("count") == 1  # Still 1, not incremented
    assert call_count[0] == 1  # Only called once

    # Cleanup
    _exec("DELETE FROM tool_cache WHERE tool_name = ?", ("test_hit_tool",), commit=True)


@test("offline: cached_api_call returns stale data when live_fn raises and stale exists")
def test_cached_stale_fallback():
    from tools.api._base import cached_api_call
    import json

    # Insert stale record
    past = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
    _exec(
        "INSERT OR REPLACE INTO tool_cache (tool_name, params_hash, result, fetched_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("test_stale_fallback", "test_stale_hash", json.dumps({"stale": True}), past, past),
        commit=True,
    )

    def failing_fn():
        raise Exception("live failure")

    result = cached_api_call("test_stale_fallback", "test_stale_hash", failing_fn, 60)
    assert result.get("stale") == True
    assert result.get("_stale") == True
    assert result.get("_age_minutes") >= 58

    # Cleanup
    _exec("DELETE FROM tool_cache WHERE tool_name = ?", ("test_stale_fallback",), commit=True)


@test("offline: cached_api_call returns error dict when live_fn raises and no stale record")
def test_cached_no_stale():
    from tools.api._base import cached_api_call

    def failing_fn():
        raise Exception("no cache available")

    result = cached_api_call("test_no_stale_tool", "test_no_stale_hash", failing_fn, 60)
    assert "error" in result
    assert result.get("_live_failed") == True
    assert result.get("_stale") == False


@test("offline: cached_api_call returns error dict when stale_ok=False regardless of stale data")
def test_cached_stale_not_ok():
    from tools.api._base import cached_api_call
    import json

    # Insert stale record
    past = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
    _exec(
        "INSERT OR REPLACE INTO tool_cache (tool_name, params_hash, result, fetched_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("test_stale_not_ok", "test_stale_hash", json.dumps({"stale": True}), past, past),
        commit=True,
    )

    def failing_fn():
        raise Exception("live failure")

    result = cached_api_call(
        "test_stale_not_ok", "test_stale_hash", failing_fn, 60, stale_ok=False
    )
    assert "error" in result
    assert result.get("_live_failed") == True
    assert result.get("_stale") == False  # Should not return stale

    # Cleanup
    _exec("DELETE FROM tool_cache WHERE tool_name = ?", ("test_stale_not_ok",), commit=True)


@test("offline: stale_notice returns None for fresh result")
def test_stale_notice_fresh():
    from tools.api._base import stale_notice
    result = {"_stale": False, "data": "fresh"}
    notice = stale_notice(result)
    assert notice is None


@test("offline: stale_notice returns string for stale result with correct age format")
def test_stale_notice_format():
    from tools.api._base import stale_notice

    # Test minutes
    result = {"_stale": True, "_age_minutes": 30, "_cached_at": "2026-05-30T10:00:00"}
    notice = stale_notice(result)
    assert "30m ago" in notice
    assert "⚠️" in notice

    # Test hours
    result = {"_stale": True, "_age_minutes": 120, "_cached_at": "2026-05-30T08:00:00"}
    notice = stale_notice(result)
    assert "2h ago" in notice

    # Test days
    result = {"_stale": True, "_age_minutes": 3000, "_cached_at": "2026-05-27T10:00:00"}
    notice = stale_notice(result)
    assert "2d ago" in notice


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
