# Personal Tasks System Software Design Document

## 1. Architecture Overview

PrivyBot's personal tasks system is a standalone to-do and reminder system with recurrence, Google Tasks sync, and natural language parsing. It spans two layers: the DB layer (`infra/db/personal_tasks.py`) for CRUD operations and the tool layer (`tools/productivity/personal.py`) for natural language parsing and event-driven sync. Sync orchestration lives in `tools/productivity/sync.py`.

```
infra/db/personal_tasks.py
  add_personal_task()           — INSERT OR IGNORE with dedup
  get_personal_tasks()          — Filter by today/upcoming/overdue/all
  get_tasks_due_soon()         — Tasks due within N minutes
  complete_personal_task()     — Mark done, generate next occurrence if recurring
  snooze_personal_task()        — Push due_datetime forward by N minutes
  delete_personal_task()        — Soft delete (status='cancelled')
  push_missed_tasks()          — Nightly job, collision handling
  next_recurrence_date()       — Compute next date from anchor
  _calc_next_due()             — Full recurrence calculation
  set_google_task_id()         — Link to Google Tasks
  get_unsynced_tasks()         — Tasks without google_task_id
  get_tasks_completed_since()  — Tasks completed after timestamp with google_task_id
  update_sync_record()         — Update tasks_sync table
  get_last_sync()              — Get sync state
  mark_reminded()              — Record reminder in task_reminders
  already_reminded()           — Check if reminded in last 60 minutes

tools/productivity/personal.py
  parse_natural_deadline()      — Parse "tomorrow at 6PM" into {date, time}
  parse_recurrence()           — Parse "every Monday" into "weekly:monday"
  add_personal_task()          — Tool wrapper with natural language + event-driven push
  list_personal_tasks()        — Tool wrapper for listing
  complete_personal_task()     — Tool wrapper with event-driven completion push
  snooze_personal_task()        — Tool wrapper
  delete_personal_task()        — Tool wrapper

tools/productivity/sync.py
  get_or_cache_tasklist_id()   — Cached tasklist_id from DB or fetch from Google
  push_new_tasks()             — Push unsynced local tasks to Google
  push_completions()           — Push local completions back to Google
  pull_from_google()            — Pull Google Tasks into local DB
  run_sync()                   — Full sync cycle (push new, push completions, pull)
```

**Key Principles:**
- **DB/tool separation**: DB layer does pure CRUD, tool layer does parsing and sync
- **Event-driven sync**: Add/complete triggers immediate push to Google, heartbeat does pull
- **Deduplication**: UNIQUE partial index on (title, due_date) WHERE status='pending' (ADR-030)
- **Recurrence**: Never-same-day rule for weekly patterns
- **Collision handling**: push_missed_tasks() deletes old row if collision detected
- **Bidirectional sync**: Local ↔ Google Tasks via google_task_id linking
- **Reminder dedup**: 60-minute window via task_reminders table

## 2. Responsibilities

### DB Layer (infra/db/personal_tasks.py)
- **CRUD operations**: Add, list, complete, snooze, delete personal tasks
- **Recurrence calculation**: next_recurrence_date(), _calc_next_due() for all patterns
- **Missed task handling**: push_missed_tasks() with collision detection
- **Google Tasks linking**: set_google_task_id(), get_unsynced_tasks(), get_tasks_completed_since()
- **Sync state tracking**: update_sync_record(), get_last_sync() via tasks_sync table
- **Reminder tracking**: mark_reminded(), already_reminded() via task_reminders table
- **Due time computation**: _compute_due_datetime() combines date and time

### Tool Layer (tools/productivity/personal.py)
- **Natural language parsing**: parse_natural_deadline() for dates/times, parse_recurrence() for patterns
- **Event-driven sync**: add_personal_task() pushes to Google immediately, complete_personal_task() pushes completion
- **Tool wrappers**: BaseTool pattern return shapes (ok, stale_notice)
- **Input validation**: Handles ISO dates vs natural language

### Sync Layer (tools/productivity/sync.py)
- **Tasklist ID caching**: get_or_cache_tasklist_id() from DB or Google
- **Push new tasks**: push_new_tasks() pushes unsynced local tasks to Google
- **Push completions**: push_completions() pushes local completions back to Google
- **Pull from Google**: pull_from_google() pulls new Google Tasks into local DB
- **Full sync cycle**: run_sync() orchestrates push new, push completions, pull
- **Error handling**: update_sync_record(error=True) on failure

## 3. What It Does NOT Do

- **No user interaction**: All operations are via tool calls, no direct UI
- **No calendar integration**: Separate from goals/tasks system
- **No collaboration**: Single-user system, no sharing
- **No complex dependencies**: Tasks are standalone, no parent/child relationships
- **No priority levels**: All tasks are equal priority
- **No tags/labels**: Only title, notes, due date/time, recurrence

## 4. Key Functions and Their Roles

### DB Layer Functions

**add_personal_task(title, due_date, due_time, recurrence, notes, reminder_minutes)**
- **Purpose**: Insert new personal task
- **Deduplication**: INSERT OR IGNORE (UNIQUE partial index on title+due_date WHERE status='pending')
- **Initial next_due**: Set to due_datetime if provided
- **Returns**: task_id (lastrowid)

**get_personal_tasks(filter)**
- **Purpose**: List tasks by filter
- **Filters**: today (due_date = today), upcoming (today to +7 days), overdue (due_date < today), all (all pending)
- **Ordering**: due_date ASC, due_time ASC, id ASC
- **Returns**: list[dict] with all task fields

**get_tasks_due_soon(minutes)**
- **Purpose**: Get tasks due within N minutes
- **Query**: due_datetime BETWEEN now AND now + N minutes, status='pending'
- **Used by**: heartbeat_check() for reminders
- **Returns**: list[dict]

**complete_personal_task(task_id)**
- **Purpose**: Mark task done, generate next occurrence if recurring
- **Flow**:
  1. Fetch task by id
  2. UPDATE status='done', completed_at=CURRENT_TIMESTAMP
  3. If recurring: calculate next_due via _calc_next_due(), INSERT OR REPLACE new task
- **Returns**: dict with status, id, title, next_due, google_task_id

**snooze_personal_task(task_id, minutes)**
- **Purpose**: Push due_datetime forward by N minutes
- **Flow**:
  1. Fetch task by id
  2. Parse current due_datetime (fallback to now)
  3. Add minutes, format as YYYY-MM-DD HH:MM
  4. UPDATE due_datetime, due_date, due_time
- **Returns**: dict with status, id, new_due

**delete_personal_task(task_id)**
- **Purpose**: Soft delete task
- **Behavior**: UPDATE status='cancelled' (not DELETE)
- **Returns**: dict with status, id

**push_missed_tasks()**
- **Purpose**: Nightly job to push forward missed tasks
- **Query**: due_date < today AND status='pending'
- **Logic**:
  - Recurring: next_recurrence_date(recurrence, anchor=today)
  - Non-recurring: today + 1 day
- **Collision handling**:
  - If same title already pending at new_date: DELETE old row
  - Else: UPDATE old row to new_date
- **Returns**: list[dict] with id, title, old_date, new_date

**next_recurrence_date(recurrence, anchor)**
- **Purpose**: Compute next recurrence date from anchor
- **Supported formats**:
  - "daily" → anchor + 1 day
  - "weekly:monday" → next Monday, never same day
  - Unknown format → anchor + 1 day (safe fallback)
- **Never-same-day rule**: If anchor is already target weekday, return anchor + 7 days
- **Returns**: YYYY-MM-DD string

**_calc_next_due(recurrence, from_date)**
- **Purpose**: Full recurrence calculation for all patterns
- **Supported formats**:
  - "daily" → +1 day
  - "weekdays" → next weekday (skip Sat/Sun)
  - "weekends" → next weekend day (skip Mon-Fri)
  - "weekly:monday,tuesday" → next occurrence of any listed day
  - "monthly:15" → 15th of next month (clamped to max day)
  - "monthly" → same day of next month
  - "interval:7" → +7 days
- **Returns**: YYYY-MM-DD string or None

**set_google_task_id(task_id, google_task_id)**
- **Purpose**: Link local task to Google Tasks
- **Behavior**: UPDATE personal_tasks SET google_task_id = ?

**get_unsynced_tasks()**
- **Purpose**: Tasks with no google_task_id that are still pending
- **Query**: google_task_id IS NULL AND status='pending'
- **Used by**: push_new_tasks()
- **Returns**: list[dict]

**get_tasks_completed_since(since)**
- **Purpose**: Tasks completed after timestamp with google_task_id set
- **Query**: completed_at >= since AND google_task_id IS NOT NULL
- **Used by**: push_completions()
- **Returns**: list[dict]

**update_sync_record(last_pull, last_push, tasklist_id, error)**
- **Purpose**: Update tasks_sync table
- **Behavior**: INSERT if no row exists, UPDATE with increment counters if exists
- **Counters**: pull_count, push_count, error_count
- **Returns**: None

**get_last_sync()**
- **Purpose**: Get sync state from tasks_sync table
- **Returns**: dict or None

**mark_reminded(task_id)**
- **Purpose**: Record reminder in task_reminders table
- **Behavior**: INSERT INTO task_reminders (task_id)
- **Returns**: None

**already_reminded(task_id)**
- **Purpose**: Check if reminded in last 60 minutes
- **Query**: reminded_at > datetime('now', '-60 minutes')
- **Returns**: bool

### Tool Layer Functions

**parse_natural_deadline(text)**
- **Purpose**: Parse natural language date/time into {date, time}
- **Supported patterns**:
  - ISO date: "2025-05-30"
  - Relative: "today", "tomorrow", "next week"
  - Day names: "Monday", "Tuesday", etc.
  - Time: "at 6PM", "at 9:30am"
- **Returns**: {"date": "YYYY-MM-DD" or None, "time": "HH:MM" or None}

**parse_recurrence(text)**
- **Purpose**: Detect recurrence pattern in natural language
- **Supported patterns**:
  - "every day" / "daily" → "daily"
  - "every weekday" / "every work day" → "weekdays"
  - "every weekend" → "weekends"
  - "every N day" / "every N week" → "interval:N"
  - "every Monday" → "weekly:monday"
  - "every week" → "weekly:{current_day}"
  - "every month" / "monthly" → "monthly"
- **Returns**: pattern string or None

**add_personal_task(title, due, time, recurrence, notes)**
- **Purpose**: Tool wrapper with natural language parsing + event-driven push
- **Flow**:
  1. Parse due date/time if natural language
  2. Parse recurrence if natural language
  3. Call DB add_personal_task()
  4. Event-driven: push to Google Tasks immediately
  5. Set google_task_id if push succeeds
- **Returns**: dict with status, id, title, due, recurrence

**list_personal_tasks(filter)**
- **Purpose**: Tool wrapper for listing tasks
- **Returns**: dict with filter, count, tasks list

**complete_personal_task(task_id)**
- **Purpose**: Tool wrapper with event-driven completion push
- **Flow**:
  1. Call DB complete_personal_task()
  2. Event-driven: push completion to Google if google_task_id exists
- **Returns**: dict from DB layer

**snooze_personal_task(task_id, minutes)**
- **Purpose**: Tool wrapper for snoozing
- **Returns**: dict from DB layer

**delete_personal_task(task_id)**
- **Purpose**: Tool wrapper for deletion
- **Returns**: dict from DB layer

### Sync Layer Functions

**get_or_cache_tasklist_id()**
- **Purpose**: Return cached tasklist_id from DB or fetch from Google
- **Flow**:
  1. Check tasks_sync table for tasklist_id
  2. If not found, call get_default_tasklist_id()
  3. Cache result in tasks_sync table
- **Returns**: tasklist_id string or None

**push_new_tasks()**
- **Purpose**: Push unsynced local tasks to Google Tasks
- **Flow**:
  1. Get tasklist_id
  2. Get unsynced tasks (google_task_id IS NULL)
  3. For each task: push_task(), set_google_task_id()
- **Returns**: count pushed

**push_completions()**
- **Purpose**: Push local completions back to Google Tasks
- **Flow**:
  1. Get tasklist_id
  2. Get tasks completed since last_push (or 2 hours ago)
  3. For each task: complete_task()
- **Returns**: count pushed

**pull_from_google()**
- **Purpose**: Pull Google Tasks into local personal_tasks DB
- **Flow**:
  1. Get tasklist_id
  2. Pull tasks from Google
  3. Filter out tasks already in local DB (by google_task_id)
  4. Filter out completed tasks
  5. For each new task: add_personal_task(), set_google_task_id()
  6. Update sync record with last_pull
- **Returns**: count of new tasks

**run_sync()**
- **Purpose**: Full sync cycle
- **Flow**:
  1. push_new_tasks()
  2. push_completions()
  3. pull_from_google()
  4. Update sync record with last_push
- **Error handling**: update_sync_record(error=True) on exception
- **Returns**: dict with status, pushed_new, pushed_completions, pulled_new

## 5. Patterns and Conventions

### DB/Tool Separation
- **DB layer**: Pure CRUD, no parsing, no sync logic
- **Tool layer**: Natural language parsing, event-driven sync
- **Sync layer**: Orchestration of bidirectional sync

### Deduplication
- **UNIQUE partial index**: (title, due_date) WHERE status='pending' (ADR-030)
- **INSERT OR IGNORE**: add_personal_task() uses INSERT OR IGNORE
- **Collision handling**: push_missed_tasks() deletes old row if collision detected

### Recurrence Patterns
- **Never-same-day rule**: next_recurrence_date() adds 7 days if anchor is already target weekday
- **Safe fallback**: Unknown formats default to +1 day
- **Comprehensive support**: daily, weekdays, weekends, weekly:day, monthly, interval:N

### Natural Language Parsing
- **Date patterns**: ISO dates, relative (today, tomorrow, next week), day names
- **Time patterns**: "at 6PM", "at 9:30am" (meridiem handling)
- **Recurrence patterns**: "every day", "every Monday", "every 2 weeks", etc.
- **Fallback**: Unrecognized patterns return None

### Event-Driven Sync
- **Add task**: Immediately push to Google Tasks (try/except, fail silently)
- **Complete task**: Immediately push completion to Google (try/except, fail silently)
- **Heartbeat**: pull_from_google() runs on polling cycle (google_tasks key, 5min interval)

### Reminder Deduplication
- **60-minute window**: already_reminded() checks task_reminders table
- **Record on send**: mark_reminded() inserts into task_reminders
- **Used by**: heartbeat_check() for personal task reminders

### Soft Delete
- **delete_personal_task()**: Sets status='cancelled' instead of DELETE
- **Purpose**: Preserve history, allow recovery if needed

### Timestamp Format
- **DB layer**: strftime("%Y-%m-%d %H:%M:%S") for datetime fields
- **Sync layer**: isoformat() for last_pull/last_push
- **Google Tasks**: ISO format, truncated to date for due_date

### Return Shapes
- **Tool layer**: BaseTool pattern (ok, stale_notice)
- **DB layer**: dict with status, id, title, etc.
- **Sync layer**: dict with status, counts, error

## 6. Data Flow

### Add Task Flow
```
User command: "add task Call mom tomorrow at 6PM every week"
    ↓
tools/productivity/personal.py: add_personal_task()
    ↓
parse_natural_deadline("tomorrow at 6PM") → {date: "2025-05-31", time: "18:00"}
parse_recurrence("every week") → "weekly:friday"
    ↓
infra/db/personal_tasks.py: add_personal_task()
    ↓
INSERT OR IGNORE INTO personal_tasks (title, due_date, due_time, recurrence, ...)
    ↓
Event-driven: push_task() to Google Tasks
    ↓
set_google_task_id(task_id, google_task_id)
    ↓
Return {"status": "added", "id": ..., "due": "2025-05-31 18:00", "recurrence": "weekly:friday"}
```

### Complete Task Flow
```
User command: "complete task 123"
    ↓
tools/productivity/personal.py: complete_personal_task()
    ↓
infra/db/personal_tasks.py: complete_personal_task()
    ↓
UPDATE personal_tasks SET status='done', completed_at=CURRENT_TIMESTAMP
    ↓
If recurring: _calc_next_due() → INSERT OR REPLACE new task
    ↓
Event-driven: complete_task() to Google Tasks (if google_task_id exists)
    ↓
Return {"status": "completed", "id": 123, "title": "...", "next_due": "..."}
```

### Sync Flow (Heartbeat)
```
PollingManager: google_tasks key (5min interval)
    ↓
tools/productivity/sync.py: run_sync()
    ↓
push_new_tasks() → get_unsynced_tasks() → push_task() → set_google_task_id()
    ↓
push_completions() → get_tasks_completed_since() → complete_task()
    ↓
pull_from_google() → pull_tasks() → add_personal_task() → set_google_task_id()
    ↓
update_sync_record(last_push=...)
    ↓
Return {"status": "ok", "pushed_new": N, "pushed_completions": M, "pulled_new": K}
```

### Missed Task Push Flow (Nightly)
```
bot/scheduler.py: nightly_summary() at 23:59
    ↓
infra/db/personal_tasks.py: push_missed_tasks()
    ↓
SELECT * FROM personal_tasks WHERE due_date < today AND status='pending'
    ↓
For each missed task:
    ↓
If recurring: next_recurrence_date(recurrence, today)
Else: tomorrow
    ↓
Collision check: SELECT id FROM personal_tasks WHERE title=? AND due_date=? AND id!=?
    ↓
If collision: DELETE old row
Else: UPDATE old row to new_date
    ↓
Return list of pushed tasks
    ↓
Send nudges via Telegram
```

## 7. Error Handling Contract

### DB Layer
- **Not found**: complete_personal_task(), snooze_personal_task(), delete_personal_task() return {"error": "Task not found: {id}"}
- **Unknown recurrence**: next_recurrence_date() returns tomorrow (safe fallback)
- **Parse errors**: _calc_next_due() returns None on exception
- **Sync errors**: update_sync_record(error=True) on exception

### Tool Layer
- **Parse failures**: parse_natural_deadline() returns {date: None, time: None}
- **Unknown recurrence**: parse_recurrence() returns None
- **Sync failures**: Event-driven push/complete try/except, fail silently (local task created/completed)

### Sync Layer
- **No tasklist_id**: push_new_tasks(), push_completions(), pull_from_google() return 0
- **API failures**: run_sync() catches exception, update_sync_record(error=True), returns {"status": "error", "error": str(e)}
- **Missing fields**: pull_from_google() skips tasks without title or completed tasks

### Reminder System
- **No reminder record**: already_reminded() returns False
- **Collision handling**: push_missed_tasks() deletes old row if collision detected (no error)

## 8. Testing Strategy

### Test Coverage
- **scripts/verify.py**: 204/204 tests pass
- **Personal tasks tests**: add, list, complete, snooze, delete, recurrence, push_missed_tasks
- **Sync tests**: google_tasks_api credentials, pull_tasks, push_task, run_sync, tasks_sync table
- **Parsing tests**: parse_natural_deadline, parse_recurrence

### Test Categories
- **Personal**: personal_tasks table, task_reminders table, add_personal_task, list_personal_tasks, complete_personal_task, snooze, get_tasks_due_soon, parse_natural_deadline, parse_recurrence, next_recurrence_date, push_missed_tasks, collision handling
- **Sync**: google_tasks_api credentials, get_default_tasklist_id, pull_tasks, push_task, tasks_sync table, run_sync, pull_from_google, push_new_tasks, push_to_google

### Test Execution
- **Command**: `uv run python scripts/verify.py`
- **Pass criteria**: 204/204 tests pass
- **Deploy gate**: Must pass before GitHub commit

## 9. Related ADRs
- ADR-030: Deduplication Strategy (UNIQUE partial index on personal_tasks)
- ADR-031: Missed Task Push-Forward and Recurrence Recovery
