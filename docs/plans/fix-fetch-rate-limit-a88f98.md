# Fix Fetch Rate Limit Test Failures

Raise fetch rate limit from 10 to 60 requests/minute and add setup/teardown to reset rate limit state in fetch tests.

## Changes

**1. core/rate_limits.py:**
- Change `LIMITS["fetch"]["requests_per_minute"]` from 10 to 60
- 10/min is too tight for a personal bot that may fetch multiple URLs in a session
- 60/min is still protective against abuse

**2. tests/test_fetch_think.py:**
- Add `_setup()` function to reset fetch rate limit state before tests run
- Add `_teardown()` function to reset fetch rate limit state after tests complete
- Call `_setup()` at top of file before any fetch tests
- Call `_teardown()` at end of file after all tests complete

**Setup/teardown implementation:**
```python
def _reset_fetch_rate_limit():
    from core.db.rate_limits_db import upsert_api_state
    upsert_api_state(
        "fetch",
        calls_this_minute=0,
        last_429_at=None,
        retry_after_seconds=0
    )

# Call before tests
_reset_fetch_rate_limit()

# Call after tests (in run_all or at end)
_reset_fetch_rate_limit()
```

## Success criteria
- `uv run python scripts/verify.py` passes 192/192
- Run twice in a row to prove rate limit state doesn't leak between runs
