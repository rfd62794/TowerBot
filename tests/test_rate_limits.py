"""Tests for RateLimitManager."""

from dotenv import load_dotenv
load_dotenv()

from core.db import init_db
init_db()

def test_decorator(name):
    def wrapper(fn):
        fn.__name__ = name
        TESTS.append((name, fn))
        return fn
    return wrapper

test = test_decorator

TESTS = []


@test("rate: api_rate_limits table exists")
def test_api_rate_limits_table_exists():
    from core.db.schema import _exec
    result = _exec("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='api_rate_limits'
    """).fetchone()
    assert result is not None, "api_rate_limits table should exist"


@test("rate: api_call_log table exists")
def test_api_call_log_table_exists():
    from core.db.schema import _exec
    result = _exec("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='api_call_log'
    """).fetchone()
    assert result is not None, "api_call_log table should exist"


@test("rate: get_api_state returns defaults for unknown API")
def test_get_api_state_defaults():
    from core.db.rate_limits_db import get_api_state
    state = get_api_state("unknown_test_api")
    assert state["api_name"] == "unknown_test_api"
    assert state["calls_today"] == 0
    assert state["calls_this_minute"] == 0
    assert state["last_call_at"] is None
    assert state["last_429_at"] is None
    assert state["retry_after_seconds"] == 0
    assert state["total_calls_lifetime"] == 0
    assert state["quota_used_today"] == 0
    assert state["day_reset_at"] is None


@test("rate: record_call increments calls_today")
def test_record_call_increments_calls_today():
    from core.db.rate_limits_db import get_api_state, upsert_api_state
    from core.rate_limits import rate_limits
    
    # Clear state
    upsert_api_state("test_api", calls_today=0)
    
    rate_limits.record_call("test_api")
    state = get_api_state("test_api")
    assert state["calls_today"] == 1


@test("rate: record_call increments total_calls_lifetime")
def test_record_call_increments_total():
    from core.db.rate_limits_db import get_api_state, upsert_api_state
    from core.rate_limits import rate_limits
    
    # Clear state
    upsert_api_state("test_api2", total_calls_lifetime=0)
    
    rate_limits.record_call("test_api2")
    state = get_api_state("test_api2")
    assert state["total_calls_lifetime"] == 1


@test("rate: record_limit sets last_429_at")
def test_record_limit_sets_429():
    from core.db.rate_limits_db import get_api_state
    from core.rate_limits import rate_limits
    
    rate_limits.record_limit("test_api3", retry_after=30)
    state = get_api_state("test_api3")
    assert state["last_429_at"] is not None
    assert state["retry_after_seconds"] == 30


@test("rate: can_call returns True for unknown API")
def test_can_call_unknown_api():
    from core.rate_limits import rate_limits
    assert rate_limits.can_call("completely_unknown_api") == True


@test("rate: can_call returns False during 429 cooldown")
def test_can_call_during_cooldown():
    from core.db.rate_limits_db import get_api_state
    from core.rate_limits import rate_limits
    
    rate_limits.record_limit("test_api4", retry_after=60)
    assert rate_limits.can_call("test_api4") == False


@test("rate: can_call returns True after cooldown expires")
def test_can_call_after_cooldown():
    from core.db.rate_limits_db import get_api_state, upsert_api_state
    from core.rate_limits import rate_limits
    
    # Set retry_after to 0 to simulate expired cooldown
    rate_limits.record_limit("test_api5", retry_after=0)
    upsert_api_state("test_api5", last_429_at="2000-01-01 00:00:00")
    assert rate_limits.can_call("test_api5") == True


@test("rate: time_until_available returns 0 when no cooldown")
def test_time_until_no_cooldown():
    from core.db.rate_limits_db import get_api_state, upsert_api_state
    from core.rate_limits import rate_limits
    
    upsert_api_state("test_api6", last_429_at=None)
    assert rate_limits.time_until_available("test_api6") == 0


@test("rate: time_until_available returns >0 during cooldown")
def test_time_until_during_cooldown():
    from core.db.rate_limits_db import get_api_state
    from core.rate_limits import rate_limits
    
    rate_limits.record_limit("test_api7", retry_after=60)
    wait = rate_limits.time_until_available("test_api7")
    assert wait > 0
    assert wait <= 60


@test("rate: get_status returns list")
def test_get_status_returns_list():
    from core.rate_limits import rate_limits
    status = rate_limits.get_status()
    assert isinstance(status, list)


@test("rate: _maybe_reset_daily resets counters on new day")
def test_maybe_reset_daily():
    from core.db.rate_limits_db import get_api_state, upsert_api_state
    from core.rate_limits import rate_limits
    from datetime import datetime
    
    # Set up state with old day_reset_at
    upsert_api_state(
        "test_api8",
        calls_today=100,
        quota_used_today=500,
        day_reset_at="2000-01-01 00:00:00"
    )
    
    # Trigger reset
    now = datetime.now()
    state = get_api_state("test_api8")
    rate_limits._maybe_reset_daily("test_api8", state, now)
    
    # Verify reset
    state = get_api_state("test_api8")
    assert state["calls_today"] == 0
    assert state["quota_used_today"] == 0
    assert state["day_reset_at"].startswith(now.strftime("%Y-%m-%d"))


@test("rate: rate_limits singleton importable")
def test_singleton_importable():
    from core.rate_limits import rate_limits
    assert rate_limits is not None
    assert hasattr(rate_limits, "can_call")
    assert hasattr(rate_limits, "record_call")
    assert hasattr(rate_limits, "record_limit")


def run_all():
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
