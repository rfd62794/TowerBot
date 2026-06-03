"""Tests for PollingManager and polling_db functions."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db
init_db()

from infra.db import record_poll, get_last_poll, get_all_last_polls
from infra.polling import polling_manager

TESTS = []


def test(name: str):
    """Test decorator — registers function in TESTS list."""
    def decorator(fn):
        TESTS.append((name, fn))
        return fn
    return decorator


def run_all() -> tuple[int, int]:
    """Run all tests. Returns (passed, failed)."""
    passed = 0
    failed = 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"✓ {name}")
            passed += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            failed += 1
    return passed, failed


@test("polling: poll_log table exists")
def test_poll_log_table_exists():
    from infra.db.schema import _exec
    result = _exec("SELECT name FROM sqlite_master WHERE type='table' AND name='poll_log'").fetchone()
    assert result is not None
    assert result["name"] == "poll_log"


@test("polling: record_poll creates entry")
def test_record_poll():
    record_poll("test_key", success=True, duration_ms=100, from_cache=False)
    last = get_last_poll("test_key")
    assert last is not None
    assert last["poll_key"] == "test_key"
    assert last["success"] == 1
    assert last["duration_ms"] == 100
    assert last["from_cache"] == 0


@test("polling: get_last_poll returns None for never-polled key")
def test_get_last_poll_none():
    result = get_last_poll("never_polled_key_xyz")
    assert result is None


@test("polling: get_last_poll returns dict after record_poll")
def test_get_last_poll_dict():
    record_poll("test_key_2", success=True, duration_ms=200, from_cache=True)
    result = get_last_poll("test_key_2")
    assert result is not None
    assert isinstance(result, dict)
    assert "poll_key" in result
    assert "polled_at" in result
    assert "success" in result
    assert "duration_ms" in result


@test("polling: get_all_last_polls returns list")
def test_get_all_last_polls():
    record_poll("test_key_3", success=True, duration_ms=50)
    result = get_all_last_polls()
    assert isinstance(result, list)
    assert len(result) > 0


@test("polling: polling_manager singleton importable")
def test_polling_manager_singleton():
    from infra.polling import polling_manager as pm2
    assert polling_manager is pm2  # Same instance


@test("polling: polling_manager.register() adds to registry")
def test_polling_manager_register():
    def dummy_fn():
        return {"ok": True}
    
    polling_manager.register("test_poll", dummy_fn, interval_seconds=60)
    assert "test_poll" in polling_manager._registry
    assert polling_manager._registry["test_poll"]["fn"] == dummy_fn
    assert polling_manager._registry["test_poll"]["interval_seconds"] == 60


@test("polling: polling_manager.status() returns list")
def test_polling_manager_status():
    status = polling_manager.status()
    assert isinstance(status, list)


@test("polling: polling_manager.status() shows registered keys")
def test_polling_manager_status_keys():
    def dummy_fn():
        return {"ok": True}
    
    polling_manager.register("status_test_key", dummy_fn, interval_seconds=120)
    status = polling_manager.status()
    keys = [s["key"] for s in status]
    assert "status_test_key" in keys


@test("polling: wait_for() returns True when no poll in progress")
def test_wait_for_no_poll():
    import asyncio
    async def test():
        result = await polling_manager.wait_for("nonexistent_key", timeout=1.0)
        return result
    result = asyncio.run(test())
    assert result is True


@test("polling: wait_for() returns False after timeout (mock in-progress)")
def test_wait_for_timeout():
    import asyncio
    async def test():
        # Mock in-progress poll by setting event
        event = asyncio.Event()
        polling_manager._poll_events["timeout_test"] = event
        
        result = await polling_manager.wait_for("timeout_test", timeout=0.1)
        
        # Clean up
        del polling_manager._poll_events["timeout_test"]
        return result
    result = asyncio.run(test())
    assert result is False


@test("polling: register_defaults() registers at least 4 keys")
def test_register_defaults():
    polling_manager.register_defaults()
    count = len(polling_manager._registry)
    assert count >= 4


@test("polling: _is_due() returns True for key never polled")
def test_is_due_never_polled():
    import asyncio
    from datetime import datetime
    
    def dummy_fn():
        return {"ok": True}
    
    polling_manager.register("is_due_test", dummy_fn, interval_seconds=60)
    
    async def test():
        result = await polling_manager._is_due("is_due_test", 60, datetime.now())
        return result
    result = asyncio.run(test())
    assert result is True
