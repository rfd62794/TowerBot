# RateLimitManager Implementation Plan

Implement ADR-026: RateLimitManager for proactive API rate limit tracking. Add two DB tables, create RateLimitManager class, integrate with BaseAPIHandler, update /status command, add tests. Target: 179/179 tests passing.

## Part 1: DB Schema (core/db/schema.py)
Add two tables to init_db():
- api_rate_limits: tracks per-API state (calls_today, calls_this_minute, last_429_at, retry_after_seconds, etc.)
- api_call_log: logs all API calls with timestamp, cost, success, response_code, was_cached
- Use TEXT timestamps with strftime('%Y-%m-%d %H:%M:%S','now') format
- Add index on api_call_log(api_name, called_at DESC)

## Part 2: DB Functions (core/db/rate_limits_db.py)
New file with rate limit DB operations:
- get_api_state(api_name): Get current state or defaults
- upsert_api_state(api_name, **fields): Update or insert
- log_api_call(api_name, cost_units, success, response_code, was_cached): Log call
- get_call_log(api_name, limit): Get recent call history
- get_all_api_states(): Get all API states

## Part 3: RateLimitManager (core/rate_limits.py)
New file with RateLimitManager class:
- LIMITS dict: Known rate limits per API (youtube, gmail, steam, ddg, etc.)
- can_call(api): Check 429 cooldown, per-minute limit, daily quota
- record_call(api, cost): Record successful call, update counters
- record_limit(api, retry_after): Record 429, set cooldown
- time_until_available(api): Seconds until next call allowed
- get_status(): Return status for all APIs (used by /status)
- _maybe_reset_daily(): Reset daily counters at midnight
- Singleton: rate_limits = RateLimitManager()

## Part 4: Exports (core/db/__init__.py)
Add rate limit functions to imports and __all__ list

## Part 5: BaseAPIHandler Integration (tools/api/_handler.py)
Update call() method:
- Check rate_limits.can_call() before live call
- If rate limited: try stale fallback, return error with _rate_limited flag
- Call live_fn() FIRST, then record_call() on success only
- Detect 429 in exception message using robust _extract_retry_after() helper
- _extract_retry_after() tries multiple patterns: retry_after_seconds, Retry-After header, retry.after
- Call rate_limits.record_limit() on 429 with extracted retry_after

## Part 6: /status Update (core/router.py)
Add rate limit status to handle_status():
- Call rate_limits.get_status()
- Show "⚠️ Rate limited: [apis]" if any unavailable
- Show "✅ All APIs available" if all good

## Part 7: Tests (tests/test_rate_limits.py)
14 tests:
- Tables exist
- get_api_state defaults
- record_call increments
- record_limit sets 429 state
- can_call True for unknown API
- can_call False during cooldown
- can_call True after cooldown
- time_until_available returns correct values
- get_status returns list
- _maybe_reset_daily resets counters
- Singleton importable

## Part 8: Verify Integration
Add test_rate_limits.py to scripts/verify.py TEST_FILES

## Part 9: Verification
Run uv run python scripts/verify.py — expect 179/179 passed

## Part 10: Spot Check
Test RateLimitManager with unknown API, 429 recording, status report

## Files
New:
- core/rate_limits.py
- core/db/rate_limits_db.py
- tests/test_rate_limits.py

Modified:
- core/db/schema.py (2 tables)
- core/db/__init__.py (exports)
- tools/api/_handler.py (call() update)
- core/router.py (/status update)
- scripts/verify.py (test file)
