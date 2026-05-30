"""Tests for core/cache.py — CacheManager class."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from core.db import init_db
init_db()

from core.cache import cache

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


@test("cache: hash() returns consistent string")
def test_hash_consistent():
    h1 = cache.hash()
    h2 = cache.hash()
    assert isinstance(h1, str), "Expected string"
    assert h1 == h2, "Hash should be consistent for same params"


@test("cache: hash('a') differs from hash('b')")
def test_hash_different():
    h1 = cache.hash("a")
    h2 = cache.hash("b")
    assert h1 != h2, "Different params should produce different hashes"


@test("cache: hash(days=7) differs from hash(days=28)")
def test_hash_kwargs():
    h1 = cache.hash(days=7)
    h2 = cache.hash(days=28)
    assert h1 != h2, "Different kwargs should produce different hashes"


@test("cache: get() returns None for unknown key")
def test_get_unknown():
    result = cache.get("unknown_key", "unknown_hash")
    assert result is None, "Expected None for unknown key"


@test("cache: set() then get() round trip")
def test_set_get_roundtrip():
    test_data = {"value": 42, "name": "test"}
    cache.set("test_key", "test_hash", test_data)
    result = cache.get("test_key", "test_hash")
    assert result is not None, "Expected cached data"
    assert result["value"] == 42, "Expected value to match"
    assert result["_stale"] is False, "Expected _stale=False for fresh data"
    cache.invalidate("test_key", "test_hash")


@test("cache: get() returns None after TTL expired")
def test_get_expired():
    from core.db.schema import _exec
    from datetime import datetime, timedelta

    # Insert with past timestamp
    past_time = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    _exec(
        """
        INSERT INTO tool_cache (tool_name, params_hash, result, expires_at, fetched_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        ["test_expired", "expired_hash", '{"value": 99}', past_time, past_time],
    )

    result = cache.get("test_expired", "expired_hash")
    assert result is None, "Expected None for expired cache"
    cache.invalidate("test_expired", "expired_hash")


@test("cache: get_or_stale() returns None when never cached")
def test_get_or_stale_never_cached():
    result = cache.get_or_stale("never_cached", "never_hash")
    assert result is None, "Expected None when never cached"


@test("cache: get_or_stale() returns stale data after TTL expired")
def test_get_or_stale_stale():
    from core.db.schema import _exec
    from datetime import datetime, timedelta

    # Insert with past timestamp
    past_time = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    _exec(
        """
        INSERT INTO tool_cache (tool_name, params_hash, result, expires_at, fetched_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        ["test_stale", "stale_hash", '{"value": 88}', past_time, past_time],
    )

    result = cache.get_or_stale("test_stale", "stale_hash")
    assert result is not None, "Expected stale data"
    assert result["value"] == 88, "Expected value to match"
    assert result["_stale"] is True, "Expected _stale=True for stale data"
    cache.invalidate("test_stale", "stale_hash")


@test("cache: call() returns fresh data on successful live_fn")
def test_call_fresh():
    call_count = [0]

    def live_fn():
        call_count[0] += 1
        return {"value": 123}

    result = cache.call("test_call_fresh", "hash1", live_fn)
    assert result["value"] == 123, "Expected live data"
    assert call_count[0] == 1, "Expected live_fn called once"
    cache.invalidate("test_call_fresh", "hash1")


@test("cache: call() returns cached data on second call")
def test_call_cached():
    call_count = [0]

    def live_fn():
        call_count[0] += 1
        return {"value": 456}

    # First call
    result1 = cache.call("test_call_cached", "hash2", live_fn)
    assert result1["value"] == 456
    assert call_count[0] == 1

    # Second call should hit cache
    result2 = cache.call("test_call_cached", "hash2", live_fn)
    assert result2["value"] == 456
    assert call_count[0] == 1, "Expected live_fn not called again"
    cache.invalidate("test_call_cached", "hash2")


@test("cache: call() returns stale on live failure when stale exists")
def test_call_stale_fallback():
    from core.db.schema import _exec
    from datetime import datetime, timedelta

    # Insert stale data
    past_time = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    _exec(
        """
        INSERT INTO tool_cache (tool_name, params_hash, result, expires_at, fetched_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        ["test_stale_fallback", "hash3", '{"value": 777}', past_time, past_time],
    )

    def failing_fn():
        raise Exception("API failure")

    result = cache.call("test_stale_fallback", "hash3", failing_fn, stale_ok=True)
    assert result["value"] == 777, "Expected stale data"
    assert result["_stale"] is True, "Expected _stale=True"
    cache.invalidate("test_stale_fallback", "hash3")


@test("cache: call() returns error dict on live failure with no stale data")
def test_call_no_stale():
    def failing_fn():
        raise Exception("API failure")

    result = cache.call("test_no_stale", "hash4", failing_fn, stale_ok=True)
    assert "error" in result, "Expected error dict"
    assert result["_live_failed"] is True, "Expected _live_failed=True"
    assert result["_stale"] is False, "Expected _stale=False"


@test("cache: call() returns error dict when stale_ok=False even with stale data")
def test_call_stale_not_ok():
    from core.db.schema import _exec
    from datetime import datetime, timedelta

    # Insert stale data
    past_time = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    _exec(
        """
        INSERT INTO tool_cache (tool_name, params_hash, result, expires_at, fetched_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        ["test_stale_not_ok", "hash5", '{"value": 999}', past_time, past_time],
    )

    def failing_fn():
        raise Exception("API failure")

    result = cache.call("test_stale_not_ok", "hash5", failing_fn, stale_ok=False)
    assert "error" in result, "Expected error dict"
    assert result["_live_failed"] is True, "Expected _live_failed=True"
    cache.invalidate("test_stale_not_ok", "hash5")


@test("cache: stale_notice() returns None for fresh result")
def test_stale_notice_fresh():
    result = {"_stale": False, "_cached_at": "2026-05-30 09:00:00"}
    notice = cache.stale_notice(result)
    assert notice is None, "Expected None for fresh data"


@test("cache: stale_notice() returns string containing 'ago' for stale result")
def test_stale_notice_stale():
    result = {
        "_stale": True,
        "_age_minutes": 90,
        "_cached_at": "2026-05-30 07:00:00",
    }
    notice = cache.stale_notice(result)
    assert notice is not None, "Expected notice for stale data"
    assert "ago" in notice, "Expected 'ago' in notice"


@test("cache: stale_notice() handles <60min correctly")
def test_stale_notice_minutes():
    result = {
        "_stale": True,
        "_age_minutes": 45,
        "_cached_at": "2026-05-30 08:15:00",
    }
    notice = cache.stale_notice(result)
    assert "45m ago" in notice, "Expected '45m ago' format"


@test("cache: stale_notice() handles >60min correctly")
def test_stale_notice_hours():
    result = {
        "_stale": True,
        "_age_minutes": 120,
        "_cached_at": "2026-05-30 07:00:00",
    }
    notice = cache.stale_notice(result)
    assert "2h ago" in notice, "Expected '2h ago' format"


@test("cache: invalidate() removes cached entry")
def test_invalidate():
    cache.set("test_invalidate", "hash6", {"value": 111})
    result = cache.get("test_invalidate", "hash6")
    assert result is not None, "Expected data before invalidate"

    cache.invalidate("test_invalidate", "hash6")
    result = cache.get("test_invalidate", "hash6")
    assert result is None, "Expected None after invalidate"


@test("cache: status() returns list with all TTL keys represented")
def test_status():
    status = cache.status()
    assert isinstance(status, list), "Expected list"
    assert len(status) == len(cache.TTL), "Expected one entry per TTL key"

    # Check structure
    for entry in status:
        assert "key" in entry
        assert "ttl_seconds" in entry
        assert "stale_budget_seconds" in entry


@test("cache: preload() with working fn returns loaded=1 failed=0")
def test_preload_success():
    def working_fn():
        return {"value": 222}

    tasks = [{"key": "test_preload", "fn": working_fn, "params_hash": "hash7"}]
    result = cache.preload(tasks)

    assert result["loaded"] == 1, "Expected loaded=1"
    assert result["failed"] == 0, "Expected failed=0"
    cache.invalidate("test_preload", "hash7")


@test("cache: preload() with failing fn returns loaded=0 failed=1")
def test_preload_failure():
    def failing_fn():
        raise Exception("Preload failure")

    tasks = [{"key": "test_preload_fail", "fn": failing_fn, "params_hash": "hash8"}]
    result = cache.preload(tasks)

    assert result["loaded"] == 0, "Expected loaded=0"
    assert result["failed"] == 1, "Expected failed=1"


@test("cache: All TTL keys have STALE_BUDGET entry")
def test_ttl_stale_budget_sync():
    for key in cache.TTL.keys():
        assert key in cache.STALE_BUDGET, f"Missing STALE_BUDGET for {key}"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
