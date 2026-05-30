# DB Layer Software Design Document

## 1. Architecture Overview

PrivyBot's database layer is a single SQLite database (`privy.db`) with 17 tables organized by domain. All database access is centralized through `DBManager` for retry logic and connection management. CRUD functions are split into domain-specific modules for maintainability.

```
infra/db/
  __init__.py           — Re-exports all public functions, lazy imports
  schema.py             — DB_PATH, SCHEMA, init_db(), _exec(), _conn, _lock
  manager.py            — DBManager class with retry logic, singleton db
  cache.py              — Tool result cache, model list cache, preload log
  memory.py             — Memory CRUD
  threads.py            — Thread CRUD
  messages.py           — Message CRUD
  personal_tasks.py     — Personal tasks, recurrence, push-forward, sync
  goals.py              — Goals, milestones, tasks, weekly plans, commitments
  history.py            — Channel, video, game, weather history, metadata
  deployments.py        — Deploy history tracking
  queue.py              — Task queue for proactive observations
  rate_limits_db.py     — API rate limit state and call logging
  polling_db.py         — Polling log tracking
  models.py             — Model throttle tracking
```

**Key Principles:**
- Single SQLite database for all state
- Centralized schema definition in `schema.py`
- DBManager wraps all access with retry logic
- Domain-specific modules for CRUD operations
- Lazy imports in `__init__.py` to avoid circular dependencies
- WAL mode for concurrent access
- Thread-safe via global lock

## 2. Responsibilities

### Core Responsibilities
- **Persistence**: All bot state stored in SQLite (threads, messages, memory, tasks, history, cache, queue, etc.)
- **Schema Management**: Table definitions, indexes, migrations in `schema.py`
- **CRUD Operations**: Create, read, update, delete for all 17 tables
- **Connection Management**: Single global connection with WAL mode, thread-safe lock
- **Retry Logic**: DBManager retries on lock errors with exponential backoff
- **Cache Management**: Tool result cache, model list cache, preload log
- **Historical Data**: Channel, video, game, weather history tables
- **Task Queue**: Proactive observation queue with priority routing
- **Deploy Tracking**: Deploy history with verify/stable/rollback markers
- **Rate Limit State**: API rate limit tracking and call logging
- **Polling Log**: Poll execution tracking
- **Model Throttle**: Model 429 tracking and cooldown management

### Domain-Specific Modules
- **memory.py**: Agent memory (key-value pairs with layers)
- **threads.py**: Telegram thread-per-chat mapping
- **messages.py**: Conversation history per thread
- **personal_tasks.py**: Standalone to-dos, reminders, recurring tasks, Google Tasks sync
- **goals.py**: Goals, milestones, tasks, weekly plans, commitments
- **history.py**: Historical metrics (channel, video, game, weather), video metadata, scheduled videos
- **deployments.py**: Deploy attempts, verify results, stable commits
- **queue.py**: Task queue for proactive observations
- **rate_limits_db.py**: API rate limit state, call logging
- **polling_db.py**: Poll execution log
- **models.py**: Model throttle tracking

## 3. What It Does NOT Do

- **No business logic**: Pure CRUD only, no domain rules
- **No API calls**: No external service communication
- **No validation beyond SQL constraints**: Application validation delegated to tool layer
- **No application-level logic**: Delegated to tool layer and bot layers
- **No authentication**: No user auth (single-user system)
- **No caching beyond tool results**: No application-level caching (delegated to CacheManager)

## 4. Key Files and Their Roles

### `__init__.py`
- **Purpose**: Re-exports all public functions for clean imports
- **Pattern**: `from infra.db import init_db, add_message, get_channel_history`
- **Lazy imports**: Cache functions imported via `_get_cache_module()` to avoid circular dependency with manager
- **Critical**: schema.py imported first to avoid circular import issues

### `schema.py`
- **DB_PATH**: `privy.db` in project root
- **SCHEMA**: All 17 table definitions as SQL string
- **init_db()**: Creates connection, enables WAL mode, executes SCHEMA, runs migrations
- **_run_migrations()**: Incremental schema migrations (personal_tasks google_task_id, commitments created_at)
- **_exec(sql, params, commit)**: Low-level SQL execution with thread lock
- **_conn**: Global sqlite3.Connection
- **_lock**: threading.Lock for thread safety
- **Timestamp format rule**: Always use `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` (SQLite space separator, not Python's T separator)

### `manager.py`
- **DBManager class**: Single owner of all database access
- **exec(sql, params, commit)**: Execute SQL with automatic retry on lock errors (5 retries, exponential backoff 0.1s → 1.6s)
- **exec_many(sql, params_list, commit)**: Batch execution
- **get_connection()**: Get current connection
- **Singleton**: `db = DBManager()`
- **Purpose**: Retry logic for concurrent access, centralized SQL execution

### `cache.py`
- **cache_model_list(models)**: Cache OpenRouter model list for 24h
- **get_cached_model_list()**: Get cached model list if within 24h
- **cache_tool_result(tool_name, params_hash, result, ttl_hours)**: Cache tool result with TTL
- **get_cached_tool_result(tool_name, params_hash)**: Get cached result if not expired
- **get_stale_cached_result(tool_name, params_hash)**: Get most recent result regardless of TTL, adds metadata (_stale, _cached_at, _age_minutes)
- **record_preload_result()**: Write to tool_cache AND preload_log (metadata tracking)
- **get_preload_status()**: Last fetch attempt per tool_name with age_minutes

### `memory.py`
- **save_memory(key, content, layer)**: INSERT OR REPLACE
- **update_memory(key, content)**: Update content and timestamp
- **retire_memory(key)**: Set active=0 (soft delete)
- **get_memories(query, limit)**: Search by key/content with LIKE, active=1
- **list_memories(layer)**: List all active memories, optional layer filter

### `threads.py`
- **create_thread(thread_id)**: Insert new thread
- **update_thread_name(thread_id, name)**: Update thread name
- **update_thread_active(thread_id)**: Update last_active timestamp
- **list_threads(limit)**: List threads by last_active DESC

### `messages.py`
- **add_message(thread_id, role, content)**: Insert message
- **get_context(thread_id, n)**: Get last N messages, reversed (oldest first)

### `personal_tasks.py`
- **add_personal_task()**: INSERT OR IGNORE (dedup via UNIQUE partial index)
- **get_personal_tasks(filter)**: Filter by today/upcoming/overdue/all
- **get_tasks_due_soon(minutes)**: Tasks due within N minutes
- **complete_personal_task()**: Mark done, generate next occurrence if recurring
- **snooze_personal_task()**: Push due_datetime forward by N minutes
- **delete_personal_task()**: Soft delete (status='cancelled')
- **push_missed_tasks()**: Nightly job, push missed tasks forward with collision handling
- **next_recurrence_date(recurrence, anchor)**: Compute next date from anchor, never-same-day rule
- **set_google_task_id()**: Link to Google Tasks
- **get_unsynced_tasks()**: Tasks without google_task_id
- **get_tasks_completed_since()**: Tasks completed after timestamp with google_task_id
- **update_sync_record()**: Update tasks_sync table
- **get_last_sync()**: Get sync state
- **mark_reminded()**: Record reminder in task_reminders
- **already_reminded()**: Check if reminded in last 60 minutes

### `goals.py`
- **upsert_goal()**: INSERT OR REPLACE
- **get_goals(status)**: List goals, optional status filter
- **get_goal(goal_id)**: Get single goal
- **upsert_milestone()**: INSERT OR REPLACE
- **get_milestones(goal_id)**: List milestones, optional goal_id filter
- **get_milestone(milestone_id)**: Get single milestone
- **upsert_task()**: INSERT OR REPLACE
- **get_tasks(status, due_date)**: List tasks, optional filters
- **get_task(task_id)**: Get single task
- **update_task_status()**: Update status, set completed_at if complete
- **get_tasks_due_today()**: Tasks due today, not complete
- **get_upcoming_scheduled(hours)**: Tasks scheduled within N hours
- **upsert_weekly_plan()**: INSERT OR REPLACE
- **get_current_weekly_plan()**: Get plan for current week
- **add_commitment()**: INSERT with 24h dedup check
- **list_commitments(status)**: List commitments, optional status filter

### `history.py`
- **record_channel_day()**: INSERT OR REPLACE (idempotent by date)
- **get_channel_history(days)**: Get last N days
- **record_video_day()**: INSERT OR REPLACE (idempotent by video_id+date)
- **get_video_history(video_id, days)**: Get last N days for video
- **record_game_day()**: INSERT OR REPLACE (idempotent by appid+date)
- **get_game_history(appid, days)**: Get last N days for game
- **record_weather_day()**: INSERT OR REPLACE (idempotent by date)
- **get_weather_history(days)**: Get last N days
- **upsert_video_metadata()**: INSERT OR REPLACE (idempotent by video_id)
- **get_video_metadata(video_id)**: Get metadata for video
- **get_all_video_metadata()**: Get all metadata
- **upsert_scheduled_video()**: INSERT OR REPLACE (idempotent by video_id)
- **get_scheduled_videos()**: Get future scheduled videos
- **clear_old_scheduled()**: Delete scheduled videos older than 7 days

### `deployments.py`
- **record_deploy(commit_hash, commit_message)**: Insert deploy record
- **mark_verify_passed(deploy_id)**: Mark verify_passed=1
- **mark_stable(deploy_id)**: Mark stable=1
- **mark_rolled_back(deploy_id)**: Mark rolled_back=1
- **get_last_stable_commit()**: Get most recent stable deploy
- **get_last_deploy()**: Get most recent deploy regardless of status
- **get_deploy_history(limit)**: Get last N deploy records

### `queue.py`
- **queue_observation()**: Queue observation with priority and scheduled time
- **get_pending_observations()**: Get unsent observations whose time has arrived
- **mark_sent()**: Mark observation as sent
- **flush_morning_queue()**: Get all unsent and mark sent

### `rate_limits_db.py`
- **get_api_state(api_name)**: Get state row, returns defaults if never seen
- **upsert_api_state(api_name, **fields)**: Update or insert API state
- **log_api_call()**: Log API call to api_call_log
- **get_call_log(api_name, limit)**: Get call log, optional api_name filter
- **get_all_api_states()**: Get all API states

### `polling_db.py`
- **record_poll()**: Record poll execution
- **get_last_poll(poll_key)**: Get most recent poll for key
- **get_all_last_polls()**: Get most recent poll for each key

### `models.py`
- **record_throttle(model_id, retry_after)**: Record 429 with ON CONFLICT DO UPDATE
- **record_success(model_id)**: Record success, reset fail_count
- **get_throttled_models()**: Get models currently in cooldown
- **get_model_status_all()**: Get all model status rows

## 5. Patterns and Conventions

### SQL Patterns
- **INSERT OR REPLACE**: Used for idempotent writes (history tables, upserts)
- **INSERT OR IGNORE**: Used for deduplication (personal_tasks UNIQUE partial index)
- **ON CONFLICT DO UPDATE**: Used for model_status (throttle tracking)
- **UNIQUE partial index**: `ux_personal_tasks_title_date WHERE status='pending'` (ADR-030)
- **Indexes**: idx_tool_cache, idx_preload_log_tool, idx_api_call_log_name_time, idx_poll_log_key_time

### Connection Management
- **Single global connection**: `_conn` in schema.py
- **Thread-safe lock**: `_lock` in schema.py
- **WAL mode**: Enabled in init_db() for concurrent access
- **DBManager retry**: 5 retries with exponential backoff (0.1s → 1.6s)

### Timestamp Format
- **Standard**: `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` (space separator)
- **SQLite CURRENT_TIMESTAMP**: Uses space separator
- **Python isoformat()**: Uses T separator
- **Rule**: Never mix formats, always use strftime for writes

### Return Shapes
- **CRUD functions**: Return `dict` or `list[dict]` (sqlite3.Row converted via dict())
- **None returns**: Return `None` for not found (e.g., get_goal())
- **Error returns**: Return `{"error": str}` for errors (e.g., complete_personal_task not found)

### Lazy Imports
- **Cache functions**: Imported via `_get_cache_module()` in __init__.py to avoid circular dependency with manager
- **Reason**: manager.py imports from schema.py, cache.py imports from manager.py

### Deduplication
- **Personal tasks**: UNIQUE partial index + INSERT OR IGNORE (ADR-030)
- **Commitments**: Application-level 24h window check (ADR-030)
- **History tables**: INSERT OR REPLACE (idempotent by date) (ADR-030)

### Recurrence
- **next_recurrence_date()**: Never-same-day rule (anchor is Monday, weekly:monday → Monday+7)
- **_calc_next_due()**: Supports daily, weekdays, weekends, weekly:day, monthly, interval:N
- **Collision handling**: push_missed_tasks() checks for existing pending task at new_date

## 6. Data Flow

```
Tool Layer (tools/*.py)
    ↓ calls
DB Layer (infra/db/*.py)
    ↓ _exec()
DBManager.exec() with retry
    ↓
SQLite (privy.db)
```

**Example flow: add_personal_task**
```
tools/personal.py: add_personal_task(title, due_date)
    ↓
infra/db/personal_tasks.py: add_personal_task(title, due_date)
    ↓
infra/db/manager.py: db.exec("INSERT OR IGNORE...", commit=True)
    ↓
infra/db/schema.py: _exec(sql, params, commit=True) with _lock
    ↓
SQLite: INSERT OR IGNORE INTO personal_tasks...
```

**Example flow: get_channel_history**
```
tools/youtube/channel.py: get_channel_summary(days=7)
    ↓
infra/db/history.py: get_channel_history(days=7)
    ↓
infra/db/manager.py: db.exec("SELECT * FROM channel_history...")
    ↓
infra/db/schema.py: _exec(sql, params) with _lock
    ↓
SQLite: SELECT * FROM channel_history...
    ↓
Return list[dict]
```

## 7. Error Handling Contract

### Lock Errors
- **DBManager**: Retries automatically on `sqlite3.OperationalError` with "locked" in message
- **Backoff**: Exponential (0.1s, 0.2s, 0.4s, 0.8s, 1.6s)
- **Max retries**: 5
- **Re-raise**: If not lock error or retries exhausted

### Not Found Errors
- **Pattern**: Return `None` for single-row queries (e.g., get_goal())
- **Pattern**: Return empty list for multi-row queries (e.g., get_goals())
- **Pattern**: Return `{"error": str}` for expected failures (e.g., complete_personal_task not found)

### SQL Errors
- **Propagation**: SQLite exceptions propagate to caller
- **Handling**: Tool layer handles and converts to error dicts

### Migration Errors
- **Pattern**: Try/except in _run_migrations(), pass on failure
- **Reason**: Migrations are additive, failure indicates column already exists

## 8. Testing Strategy

### Test Coverage
- **scripts/verify.py**: 204/204 tests pass
- **Schema tests**: All tables exist, indexes exist
- **CRUD tests**: Each module has create/read/update/delete tests
- **Edge cases**: Deduplication, recurrence, collision handling, 24h window
- **Integration tests**: Full tool → DB → SQLite flow

### Test Categories
- **Schema**: Table existence, index existence, column existence
- **Memory**: save, update, retire, get, list
- **Threads**: create, update name, update active, list
- **Messages**: add, get context
- **Personal tasks**: add (with recurrence), list, complete, snooze, get due soon, parse natural deadline, parse recurrence, next_recurrence_date, push_missed_tasks, collision handling
- **Sync**: Google Tasks sync functions
- **Calendar**: credentials, get events, get today, get schedule, get upcoming, check availability
- **Gmail**: credentials, get unread, get recent, search, get summary, search email, check sender, dual account handling
- **History**: record/get for channel, video, game, weather, metadata, scheduled videos
- **Offline**: get_stale_cached_result, record_preload_result, get_preload_status, cached_api_call, stale_notice
- **Cache**: hash, get, set, get_or_stale, call, stale_notice, invalidate, status, preload
- **Handler**: cache_key, hash, call
- **Tool**: success, error, stale_notice
- **Fetch**: fetch_url
- **Think**: think
- **Rate**: api_rate_limits table, api_call_log table, get_api_state, record_call, record_limit, can_call, time_until_available, get_status, _maybe_reset_daily
- **Polling**: poll_log table, record_poll, get_last_poll, get_all_last_polls, register_defaults, _is_due
- **Briefing**: morning_briefing runs, output sections

### Test Execution
- **Command**: `uv run python scripts/verify.py`
- **Pass criteria**: 204/204 tests pass
- **Deploy gate**: Must pass before GitHub commit

## 9. Database Schema

### Tables (17 total)
1. **threads**: Thread-per-chat mapping
2. **messages**: Conversation history
3. **memory**: Agent memory (key-value with layers)
4. **model_status**: Model throttle tracking
5. **kv_cache**: Key-value cache (model list)
6. **tool_cache**: Tool result cache
7. **preload_log**: Preload metadata tracking
8. **channel_history**: Daily channel metrics
9. **video_history**: Daily video metrics
10. **game_history**: Daily game metrics
11. **weather_history**: Daily weather data
12. **video_metadata_cache**: Video metadata
13. **scheduled_videos**: Scheduled video tracking
14. **task_queue**: Proactive observation queue
15. **goals**: Goals tracking
16. **milestones**: Milestone tracking
17. **tasks**: Task tracking
18. **weekly_plans**: Weekly plan tracking
19. **commitments**: Commitment tracking
20. **personal_tasks**: Personal tasks
21. **task_reminders**: Task reminder log
22. **tasks_sync**: Google Tasks sync state
23. **deploy_history**: Deploy tracking
24. **api_rate_limits**: API rate limit state
25. **api_call_log**: API call log
26. **poll_log**: Poll execution log

### Indexes
- **idx_tool_cache**: (tool_name, params_hash) UNIQUE
- **idx_preload_log_tool**: (tool_name, fetched_at DESC)
- **idx_api_call_log_name_time**: (api_name, called_at DESC)
- **idx_poll_log_key_time**: (poll_key, polled_at DESC)
- **ux_personal_tasks_title_date**: (title, due_date) WHERE status='pending' UNIQUE

## 10. Related ADRs
- ADR-007: SQLite as Persistence Layer
- ADR-023: DBManager Layer
- ADR-030: Deduplication Strategy
- ADR-031: Missed Task Push-Forward and Recurrence Recovery
