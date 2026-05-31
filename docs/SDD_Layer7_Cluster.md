# Layer 7 Cluster Software Design Document

## 1. Architecture Overview

PrivyBot's Layer 7 is a cluster of three singleton managers that coordinate API access, caching, and background polling. These managers replace scattered rate limit checks, cache lookups, and heartbeat data fetching with centralized, policy-driven systems.

```
infra/
  cache.py         — CacheManager singleton (cache)
  rate_limits.py   — RateLimitManager singleton (rate_limits)
  polling.py       — PollingManager singleton (polling_manager)
```

**Key Principles:**
- **Single source of truth**: Each manager owns its domain (TTL registry, rate limits, polling intervals)
- **Policy-driven**: All configuration in class-level dicts (TTL, LIMITS, INTERVALS)
- **Singleton pattern**: All layers import the singleton instance
- **Coordination**: PollingManager checks RateLimitManager before polling; tools check CacheManager before calling APIs
- **BaseAPIHandler integration**: All three managers consulted before every live API call
- **TTL/interval alignment**: PollingManager INTERVALS match CacheManager TTLs exactly

## 2. Responsibilities

### CacheManager
- **TTL registry**: Source of truth for all cache TTLs (40+ keys, 5min to 7 days)
- **Staleness budget**: Defines "too old" threshold for user-facing staleness notices
- **Cache operations**: get(), set(), get_or_stale(), invalidate()
- **call() pattern**: Main entry point for API calls with fresh cache → live call → stale fallback
- **Preloading**: Warm cache from task list (used at startup)
- **Status reporting**: Health of all cached tools (last fetch, age, success)
- **Hash generation**: Deterministic params hash for cache keys

### RateLimitManager
- **Rate limit registry**: Source of truth for API rate limits (12 APIs, various limits)
- **Pre-call checks**: can_call() checks 429 cooldown, per-minute limits, daily quotas
- **Call recording**: record_call() updates rolling counters
- **429 handling**: record_limit() sets cooldown from retry_after header
- **Time until available**: time_until_available() returns seconds until next call allowed
- **Daily reset**: _maybe_reset_daily() resets counters at midnight
- **Status reporting**: Current state of all tracked APIs (available, wait, quota used)

### PollingManager
- **Polling registry**: Source of truth for polling intervals (9 data sources, 5min to 24h)
- **Registration**: register() adds data sources with function and interval
- **Default registration**: register_defaults() registers all standard data sources at startup
- **Poll loop**: run_loop() checks every 60s which polls are due, fires as async tasks
- **Due checking**: _is_due() checks last poll time and rate limits before firing
- **Poll execution**: _run_poll() executes poll in executor, records to DB, sets event
- **Coordination**: wait_for() allows callers to wait for in-progress polls
- **Status reporting**: Current state of all registered polls (last polled, next due, overdue, in_progress)

## 3. What It Does NOT Do

- **No direct API calls**: Delegates to tool layer functions
- **No business logic**: Pure coordination and policy enforcement
- **No user interaction**: All operations are internal, no direct user messages
- **No file operations**: No direct file system access
- **No model calls**: No LLM usage
- **No decision making**: Policy is fixed in class-level dicts, no runtime decisions

## 4. Key Classes and Their Roles

### CacheManager (infra/cache.py)

**TTL Registry**
- **Purpose**: Source of truth for all cache TTLs
- **Keys**: 40+ tool names (youtube_channel, gmail_unread_personal, weather, etc.)
- **Values**: TTL in seconds (300 to 604800)
- **Default**: 3600s (1 hour) for unknown keys

**STALE_BUDGET**
- **Purpose**: Defines "too old" threshold for staleness notices
- **Values**: Usually matches TTL, but can differ
- **Usage**: stale_notice() checks if age exceeds budget

**hash(*args, **kwargs)**
- **Purpose**: Deterministic params hash for cache keys
- **Algorithm**: JSON dumps args/kwargs → MD5 hash
- **Usage**: cache.hash() for no params, cache.hash("duckov") for one param, cache.hash(days=7) for kwargs

**get(key, params_hash)**
- **Purpose**: Fresh cache hit only
- **Returns**: None if miss or expired, result with _stale=False if hit
- **Behavior**: Does NOT return stale data

**get_or_stale(key, params_hash)**
- **Purpose**: Fresh first, stale if expired
- **Returns**: None only if never cached
- **Behavior**: Calls get() first, falls back to get_stale_cached_result() if miss

**set(key, params_hash, data)**
- **Purpose**: Store with TTL from TTL policy
- **Behavior**: Sets _stale=False, calls cache_tool_result() with TTL from TTL[key]
- **Default**: 3600s for unknown keys

**call(key, params_hash, live_fn, stale_ok=True)**
- **Purpose**: Main entry point for all API calls
- **Flow**:
  1. Fresh cache hit → return immediately
  2. Live call succeeds → cache + return
  3. Live fails + stale_ok + stale exists → return stale with metadata
  4. Live fails, no stale → error dict
- **stale_ok=True**: Returns stale data on live failure
- **stale_ok=False**: Returns error dict even if stale exists
- **Returns**: dict with _stale, _age_minutes, _cached_at metadata

**stale_notice(result)**
- **Purpose**: Human-readable staleness notice
- **Returns**: None if fresh, "⚠️ Data from {age} ago ({timestamp})" if stale
- **Age formatting**: <60min = "Xm ago", <1440min = "Xh ago", else = "Xd ago"

**invalidate(key, params_hash=None)**
- **Purpose**: Clear cached data
- **Behavior**: params_hash=None clears all entries for that key
- **Implementation**: Direct DELETE from tool_cache table

**status()**
- **Purpose**: Health of all cached tools
- **Returns**: list[dict] with key, ttl_seconds, stale_budget_seconds, last_preload, last_preload_age_minutes, last_preload_success
- **Source**: preload_log table + TTL registry

**preload(tasks)**
- **Purpose**: Warm cache from task list
- **Task format**: {"key": str, "fn": callable, "params_hash": str}
- **Behavior**: Runs sequentially, records to preload_log
- **Returns**: {"loaded": int, "failed": int, "results": list}

### RateLimitManager (infra/rate_limits.py)

**LIMITS Registry**
- **Purpose**: Source of truth for rate limit policy
- **Keys**: 12 APIs (youtube, gmail, calendar, steam, ddg, wikipedia, reddit, etc.)
- **Fields**: units_per_day, cost_per_search, cost_per_list, requests_per_minute, requests_per_second, requests_per_5min, requests_per_day
- **None values**: Unknown/unlimited for that field
- **Special case**: openrouter has "handled_by": "model_manager"

**can_call(api)**
- **Purpose**: True if safe to make a live call now
- **Checks in order**:
  1. Explicit 429 cooldown active?
  2. Per-minute rate exceeded?
  3. Daily quota exhausted?
- **Unknown APIs**: Always return True (don't block what we can't measure)
- **Returns**: True if all checks pass, False otherwise

**record_call(api, cost=1)**
- **Purpose**: Record a successful API call
- **Updates**: calls_today, calls_this_minute, last_call_at, total_calls_lifetime, quota_used_today
- **Minute reset**: Resets calls_this_minute if >60s since last call
- **Logging**: Also logs to api_call_log table

**record_limit(api, retry_after=60)**
- **Purpose**: Record a 429 response
- **Sets**: last_429_at, retry_after_seconds
- **Logging**: Logs to api_call_log with response_code=429

**time_until_available(api)**
- **Purpose**: Seconds until next call allowed
- **Returns**: 0 if available now, else seconds until cooldown expires
- **Calculation**: last_429_at + retry_after_seconds - now

**get_status()**
- **Purpose**: Current state of all tracked APIs
- **Returns**: list[dict] with api, available, wait_seconds, calls_today, daily_limit, quota_used, last_429, total_calls
- **Used by**: /status command

**_maybe_reset_daily(api, state, now)**
- **Purpose**: Reset daily counters at midnight
- **Checks**: If day_reset_at doesn't start with today's date
- **Resets**: calls_today=0, quota_used_today=0, day_reset_at=now

### PollingManager (infra/polling.py)

**INTERVALS Registry**
- **Purpose**: Source of truth for polling intervals
- **Keys**: 9 data sources (gmail_personal, gmail_rfd, calendar_today, google_tasks, youtube_channel, steam_library, weather, ddg_search, wikipedia, reddit)
- **Values**: Interval in seconds (300 to 86400)
- **None values**: On-demand only, never polled
- **Alignment**: Matches CacheManager TTLs exactly

**register(key, fn, interval_seconds=None, args=None)**
- **Purpose**: Register a data source for polling
- **interval_seconds**: None = on-demand only, defaults to INTERVALS[key]
- **args**: kwargs passed to fn on each poll
- **Registry**: Stores in _registry dict

**register_defaults()**
- **Purpose**: Register all default data sources at startup
- **Imports**: Tool functions to avoid circular imports
- **Registers**: gmail_personal, gmail_rfd, calendar_today, calendar_upcoming, google_tasks, youtube_channel, steam_library, weather

**run_loop()**
- **Purpose**: Main poll loop, runs indefinitely
- **Cycle**: Checks every 60s which polls are due, fires due polls as async tasks
- **Behavior**: Skips keys with interval=None (on-demand only)

**_is_due(key, interval, now)**
- **Purpose**: Is this poll due to run?
- **Checks**:
  1. Rate limited? (calls rate_limits.can_call(api_prefix))
  2. Never polled? (return True)
  3. Interval elapsed? (last_polled_at + interval <= now)
- **Rate limit check**: Skips poll if API is rate-limited

**_run_poll(key)**
- **Purpose**: Execute one poll
- **Flow**:
  1. Set asyncio.Event in _poll_events (signals in-progress)
  2. Run fn(**args) in executor (non-blocking)
  3. Record to poll_log (success, duration_ms, from_cache, error_msg)
  4. Clear event from _poll_events
- **From cache detection**: Checks if result has _stale key (stale = not from cache)
- **Collision handling**: Returns if already polling this key

**wait_for(key, timeout=5.0)**
- **Purpose**: Wait for an in-progress poll
- **Returns**: True if completed, False if timeout or not polling
- **Used by**: morning_briefing() for time-sensitive keys (gmail_personal, gmail_rfd, calendar_today, google_tasks)
- **Timeout**: 5.0 seconds default

**status()**
- **Purpose**: Current state of all registered polls
- **Returns**: list[dict] with key, interval_seconds, last_polled, last_success, next_due, overdue, in_progress
- **Used by**: /status command

**stop()**
- **Purpose**: Graceful shutdown
- **Behavior**: Sets _running=False, loop exits on next cycle

## 5. Patterns and Conventions

### Singleton Pattern
- **All three managers**: Singleton instances exported at module level
- **Import pattern**: `from infra.cache import cache`, `from infra.rate_limits import rate_limits`, `from infra.polling import polling_manager`
- **Purpose**: Single source of truth, no duplicate instances

### Policy-Driven Configuration
- **Class-level dicts**: TTL, LIMITS, INTERVALS defined at class level
- **Source of truth**: All other code reads from these dicts
- **Phase 2 API files**: Read from CacheManager.TTL for their TTLs

### TTL/Interval Alignment
- **PollingManager.INTERVALS**: Matches CacheManager.TTL exactly
- **Purpose**: Poll at the same rate data expires from cache
- **Examples**: gmail_personal = 300s (5min), calendar_today = 900s (15min), youtube_channel = 86400s (24h)

### Stale Fallback Pattern
- **CacheManager.call()**: Fresh → Live → Stale → Error
- **stale_ok=True**: Returns stale data on live failure (default)
- **stale_ok=False**: Returns error dict even if stale exists
- **Metadata**: Stale results include _stale=True, _age_minutes, _cached_at

### Rate Limit Check Pattern
- **Pre-call check**: can_call() before every live API call
- **Three checks**: 429 cooldown, per-minute limit, daily quota
- **Unknown APIs**: Always return True (don't block what we can't measure)
- **Cooldown**: Set by record_limit() with retry_after from 429 response

### Polling Coordination Pattern
- **PollingManager._is_due()**: Checks RateLimitManager before polling
- **API prefix extraction**: key.split("_")[0] to get API name
- **Skip if rate-limited**: Don't poll if can_call() returns False
- **Collision handling**: _run_poll() returns if already polling this key

### Async Event Pattern
- **PollingManager._poll_events**: dict[str, asyncio.Event]
- **Signal in-progress**: Set event before poll, clear after
- **wait_for()**: Waiters can await event.wait() with timeout
- **Used by**: morning_briefing() to wait for time-sensitive polls

### Executor Pattern
- **PollingManager._run_poll()**: Runs fn(**args) in executor
- **Non-blocking**: Doesn't block the event loop
- **Implementation**: loop.run_in_executor(None, lambda: fn(**args))

### Logging Convention
- **Cache**: [cache] prefix (HIT, LIVE, LIVE FAIL, STALE, INVALIDATED)
- **Rate limits**: [rate] prefix (cooldown, 429 recorded, minute limit, daily quota)
- **Polling**: [poll] prefix (registered, firing, ok, failed, wait_for timeout)

### Error Handling
- **CacheManager.call()**: Returns error dict on live failure if no stale
- **RateLimitManager**: Logs warnings on limit violations
- **PollingManager**: Logs warnings on poll failures, records to poll_log
- **Graceful degradation**: Individual poll failures don't stop loop

## 6. Data Flow

### API Call Flow (BaseAPIHandler)
```
Tool layer (tools/*.py)
    ↓
BaseAPIHandler._call()
    ↓
RateLimitManager.can_call(api)
    ↓ (if True)
CacheManager.call(key, params_hash, live_fn, stale_ok)
    ↓
CacheManager.get() → fresh hit?
    ↓ (if miss)
live_fn() → actual API call
    ↓ (if success)
CacheManager.set() → cache result
    ↓ (if failure and stale_ok)
CacheManager.get_or_stale() → stale fallback
    ↓
Return result (fresh or stale or error)
```

### Polling Flow
```
PollingManager.run_loop() (60s cycle)
    ↓
For each registered key:
    ↓
PollingManager._is_due(key, interval, now)
    ↓
RateLimitManager.can_call(api_prefix)
    ↓ (if True)
Check last_polled_at + interval <= now
    ↓ (if due)
asyncio.create_task(_run_poll(key))
    ↓
PollingManager._run_poll(key)
    ↓
Set asyncio.Event in _poll_events
    ↓
Run fn(**args) in executor
    ↓
Record to poll_log (success, duration_ms, from_cache)
    ↓
Clear event from _poll_events
```

### Coordinator Flow (morning_briefing)
```
morning_briefing()
    ↓
PollingManager.wait_for("gmail_personal", timeout=5.0)
    ↓
Wait for asyncio.Event if poll in progress
    ↓ (if completed or not polling)
Continue to next key
    ↓
Repeat for gmail_rfd, calendar_today, google_tasks
    ↓
Tool layer calls (get_inbox_summary, get_today_schedule, etc.)
    ↓
CacheManager.call() → fresh from cache or live call
    ↓
Format briefing sections
```

### Preload Flow (startup)
```
privybot.py startup
    ↓
PollingManager.register_defaults()
    ↓
CacheManager.preload(tasks)
    ↓
For each task:
    ↓
Run fn()
    ↓
CacheManager.set() → cache result
    ↓
Record to preload_log (success, duration_ms)
    ↓
Return summary (loaded, failed, results)
```

## 7. Error Handling Contract

### CacheManager
- **Live call failure**: Returns error dict if stale_ok=False or no stale exists
- **Stale fallback**: Returns stale data with metadata if stale_ok=True and stale exists
- **Unknown keys**: Default TTL to 3600s (1 hour)
- **Invalidation failure**: Logs and continues (no exception)
- **Preload failure**: Counts as failed, continues to next task

### RateLimitManager
- **Unknown APIs**: can_call() returns True (don't block what we can't measure)
- **Missing state**: get_api_state() returns defaults for never-seen APIs
- **Daily reset failure**: Logs and continues (no exception)
- **429 handling**: Sets cooldown, logs warning

### PollingManager
- **Poll failure**: Logs warning, records to poll_log with error_msg, continues loop
- **Missing registry entry**: Logs and returns (no exception)
- **Rate limit skip**: Silently skips poll if can_call() returns False
- **Wait timeout**: Returns False, logs warning, caller proceeds
- **Collision handling**: Returns if already polling this key (no duplicate polls)

### Coordination Errors
- **PollingManager.wait_for() timeout**: Returns False, caller proceeds (may read stale data)
- **CacheManager.call() with no stale**: Returns error dict, caller handles
- **RateLimitManager.can_call() failure**: Returns False, caller skips API call

## 8. Testing Strategy

### Test Coverage
- **scripts/verify.py**: 204/204 tests pass
- **Cache tests**: hash(), get(), set(), get_or_stale(), call(), stale_notice(), invalidate(), status(), preload()
- **Rate limit tests**: can_call(), record_call(), record_limit(), time_until_available(), _maybe_reset_daily()
- **Polling tests**: register(), _is_due(), run_poll(), wait_for(), status(), register_defaults()

### Test Categories
- **Cache**: hash consistency, get/set round trip, TTL expiry, get_or_stale fallback, call() fresh/live/stale/error paths, stale_notice formatting, invalidate, status, preload
- **Rate limits**: api_rate_limits table, api_call_log table, get_api_state defaults, record_call increments, record_limit cooldown, can_call (unknown API, cooldown, minute limit, daily quota), time_until_available, _maybe_reset_daily, singleton import
- **Polling**: poll_log table, record_poll, get_last_poll, get_all_last_polls, register, _is_due (never polled, interval elapsed, rate-limited), wait_for (not polling, completed, timeout), status, register_defaults, singleton import
- **Briefing**: morning_briefing runs, output sections (channel stats, gmail, personal tasks, weather, weekly focus)

### Test Execution
- **Command**: `uv run python scripts/verify.py`
- **Pass criteria**: 204/204 tests pass
- **Deploy gate**: Must pass before GitHub commit

## 9. Related ADRs
- ADR-026: RateLimitManager Layer
- ADR-027: PollingManager Layer
- ADR-030: Deduplication Strategy (cache management)
