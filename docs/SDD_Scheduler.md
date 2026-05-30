# Scheduler Software Design Document

## 1. Architecture Overview

PrivyBot's scheduler is a single async loop (`run_scheduler()`) that manages periodic background tasks. It runs in parallel with the Telegram bot's polling loop, firing fixed-time tasks (morning briefing, nightly summary) and hourly heartbeat checks for proactive observations and health monitoring.

```
bot/scheduler.py
  run_scheduler()          — Main async loop, 1-minute sleep cycle
  morning_briefing()       — 7AM daily briefing with PollingManager coordination
  nightly_summary()        — 23:59 missed task push-forward
  heartbeat_check()        — Hourly proactive observations
  health_check()           — Hourly system health monitoring
  auto_rollback()          — Git rollback on critical failure
  check_missed_briefing()  — Startup recovery for missed briefings
  should_send_now()        — Time-based priority routing
  _trend()                 — Percentage trend calculation
```

**Key Principles:**
- Single async loop with 1-minute sleep cycle
- Fixed-time tasks with daily reset (fired_today tracking)
- PollingManager coordination to avoid reading stale data
- Sleep hours suppression (midnight-7AM Eastern)
- Priority-based observation routing (critical/high/normal)
- Comprehensive error handling with logging
- Startup recovery for missed briefings

## 2. Responsibilities

### Core Responsibilities
- **Morning briefing**: 7AM daily briefing with channel stats, calendar, email, tasks, weather, weekly focus
- **Nightly summary**: 23:59 missed task push-forward with collision handling
- **Heartbeat checks**: Hourly proactive observations (content gaps, game spikes, task reminders, overdue tasks)
- **Health monitoring**: Hourly system health checks (models, credentials, database, deploy status)
- **Auto-rollback**: Git rollback on critical health failure
- **Startup recovery**: Detect and send missed briefings on startup
- **Queue management**: Flush morning queue, send pending observations based on time/priority
- **Polling coordination**: Wait for PollingManager before reading time-sensitive data

### Specific Checks (Heartbeat)
1. **Content calendar gap**: Detect when scheduled videos run out (3-7 day warning)
2. **Game trend spike**: Track player count changes for monitored games (>20% spike)
3. **Task reminders**: Send reminders for tasks due within 60 minutes
4. **Overdue tasks**: Queue observations for overdue tasks
5. **Queue flush**: Send pending observations based on time/priority
6. **Personal task reminders**: Send reminders for personal tasks due within 90 minutes
7. **Calendar alerts**: Pre-event calendar reminders (60 minutes before)
8. **Daily task summary**: Daily summary of overdue and pending personal tasks

### Health Checks
1. **Model availability**: Check if any free models are available
2. **YouTube credentials**: Verify YouTube API credentials are accessible
3. **Database accessibility**: Verify database connection works
4. **Deploy status**: Check if last deploy passed verify (auto-rollback if not)

## 3. What It Does NOT Do

- **No direct Telegram API calls**: Uses injected `send_fn` for all sends
- **No data fetching**: Delegates to tool layer (tools/*.py)
- **No business logic**: Pure scheduling and coordination
- **No model calls**: No LLM usage (except anomaly detection could trigger LLM in future)
- **No user interaction**: All messages are proactive, not interactive
- **No file operations**: No direct file system access (except git rollback via subprocess)

## 4. Key Functions and Their Roles

### `run_scheduler(send_fn)`
- **Purpose**: Main async loop, runs forever
- **Timing**: 1-minute sleep cycle
- **Fixed tasks**: 07:00 morning_briefing, 23:59 nightly_summary
- **Heartbeat**: Every 60 minutes (heartbeat_check + health_check)
- **Daily reset**: fired_today dict resets at midnight
- **Logic**: Check if within 1 minute of target time and not already fired today

### `morning_briefing(send_fn)`
- **Purpose**: 7AM daily briefing
- **PollingManager coordination**: wait_for() on gmail_personal, gmail_rfd, calendar_today, google_tasks (5s timeout each)
- **Sections in order**:
  1. Overnight queue flush
  2. Channel stats (current week vs prior week, trend calculation)
  3. Anomaly detection (ratio >3.0 or <0.5)
  4. Game trend detection (tracked games with >10% change)
  5. Scheduled videos today
  6. Today's calendar events
  7. Email unread counts (personal + RFD IT)
  8. Today's tasks (goals/tasks)
  9. Personal tasks today
  10. Weather
  11. Weekly focus
- **Stale fallback**: If tool fails, logs debug and continues (no section, no crash)
- **Anomaly detection**: ratio = current/prior, anomaly if >3.0 or <0.5
- **Game trend detection**: Tracked games (Raccoin, Duckov, Scritchy Scratchy), alert if >10% change
- **Recording**: Always records to channel_history after successful send

### `nightly_summary(send_fn)`
- **Purpose**: 23:59 missed task push-forward
- **Call order**: push_missed_tasks() first, then send nudges
- **Nudge batching**: Single send for all pushed tasks (not per-task)
- **Format**: "⚠️ Missed tasks pushed forward:" followed by list
- **Collision handling**: Handled by push_missed_tasks() (ADR-031)
- **No-op**: If no missed tasks, logs and returns without sending

### `heartbeat_check(send_fn)`
- **Purpose**: Hourly proactive observations
- **Sleep hours suppression**: Runs checks but only sends critical during sleep hours
- **Priority routing**: should_send_now() determines if observation should be sent now
- **Checks**:
  1. Content calendar gap (3-7 day warning)
  2. Game trend spike (>20% change)
  3. Task reminders (within 60 minutes)
  4. Overdue tasks
  5. Queue flush (pending observations)
  6. Personal task reminders (within 90 minutes)
  7. Calendar alerts (60 minutes before)
  8. Daily task summary (overdue + pending personal tasks)
- **Error handling**: Each check wrapped in try/except, logs debug on failure

### `health_check(send_fn)`
- **Purpose**: Hourly system health monitoring
- **Checks**:
  1. Model availability (get_available_model())
  2. YouTube credentials (_get_credentials())
  3. Database accessibility (list_memories())
  4. Deploy status (last deploy verify_passed)
- **Auto-rollback**: If last deploy failed verify, calls auto_rollback()
- **Error reporting**: Sends message with all issues found

### `auto_rollback(send_fn)`
- **Purpose**: Git rollback on critical health failure
- **Flow**: Get last stable commit → git checkout → restart service → record deploy → mark stable
- **Restart**: Uses NSSM (Windows service manager)
- **Error handling**: Sends error message if no stable commit or git checkout fails

### `check_missed_briefing(send_fn)`
- **Purpose**: Startup recovery for missed briefings
- **Logic**: If current time >7AM and no channel_history entry for today, send briefing now
- **Called**: On every startup before run_scheduler()

### `should_send_now(priority)`
- **Purpose**: Time-based priority routing
- **Sleep hours (0-7AM)**: Only critical priority
- **Late night (10PM-midnight)**: Critical and high priority
- **Normal hours (7AM-10PM)**: All priorities
- **Timezone**: Eastern (America/New_York)

### `_trend(current, prior)`
- **Purpose**: Calculate percentage trend
- **Formula**: ((current - prior) / prior) * 100
- **Rounding**: Rounds before sign check (fixes -0% bug)
- **Special case**: Returns "+∞%" if prior is 0

## 5. Patterns and Conventions

### Time Handling
- **Timezone**: Eastern (America/New_York) for all time checks
- **Sleep hours**: range(0, 7) = midnight to 7AM
- **Late night**: hour >= 22 = 10PM to midnight
- **Format**: datetime.now(EASTERN) for all time checks
- **Date strings**: strftime("%Y-%m-%d") for date comparisons

### Error Handling
- **Per-section try/except**: Each briefing section wrapped independently
- **Debug logging**: logger.debug() for expected failures (tool errors)
- **Error logging**: logger.error() for unexpected failures
- **Graceful degradation**: Section fails → continue to next section (no crash)
- **Error messages**: Briefing failure sends "📺 Morning briefing failed: {error}"

### PollingManager Coordination
- **Keys**: gmail_personal, gmail_rfd, calendar_today, google_tasks
- **Timeout**: 5.0 seconds each
- **Purpose**: Wait for in-progress polls before reading time-sensitive data
- **Location**: Start of morning_briefing() before any data fetching
- **Why**: Prevent briefing from reading stale data mid-poll

### Queue Management
- **Morning queue**: flush_morning_queue() at start of briefing
- **Pending queue**: get_pending_observations() in heartbeat
- **Priority routing**: should_send_now() determines if observation should be sent now
- **Marking sent**: mark_sent() after sending
- **Batching**: Single send for all pushed tasks in nightly_summary

### Alert Deduplication
- **Personal task reminders**: already_reminded() checks task_reminders table (60-minute window)
- **Calendar alerts**: already_reminded() with zlib.adler32 hash of alert key
- **Daily task summary**: already_reminded() with date-based alert key
- **Purpose**: Prevent duplicate alerts for same event

### Trend Calculation
- **Rounding before sign**: round(pct) before sign check (fixes -0% bug)
- **Sign logic**: "+" if rounded >= 0, else ""
- **Special case**: "+∞%" if prior is 0

### Startup Recovery
- **check_missed_briefing()**: Called on startup before run_scheduler()
- **Logic**: If time >7AM and no channel_history for today, send briefing now
- **Purpose**: Recover from bot restarts during the day

## 6. Data Flow

```
run_scheduler() loop (1-minute sleep)
    ↓
Check fixed tasks (07:00, 23:59)
    ↓
morning_briefing()
    ↓
PollingManager.wait_for() (gmail_personal, gmail_rfd, calendar_today, google_tasks)
    ↓
Tool layer calls (get_channel_summary, get_today_schedule, get_all_inbox_summary, etc.)
    ↓
DB layer (get_channel_history, get_tasks_due_today, get_personal_tasks, etc.)
    ↓
Format message sections
    ↓
send_fn(msg) → Telegram
    ↓
record_channel_day() → DB
```

**Heartbeat flow:**
```
run_scheduler() loop (60-minute heartbeat)
    ↓
heartbeat_check()
    ↓
Tool layer calls (get_scheduled_videos, get_game_metrics, get_upcoming_scheduled, etc.)
    ↓
queue_observation() → DB task_queue
    ↓
get_pending_observations() → DB
    ↓
should_send_now() → time/priority check
    ↓
send_fn(msg) → Telegram
    ↓
mark_sent() → DB
```

**Health check flow:**
```
run_scheduler() loop (60-minute health check)
    ↓
health_check()
    ↓
System checks (model manager, credentials, database, deploy status)
    ↓
If issues → send_fn(msg) → Telegram
    ↓
If critical (deploy failed) → auto_rollback()
    ↓
git checkout → NSSM restart → record deploy → mark stable
```

## 7. Error Handling Contract

### Tool Errors
- **Expected failures**: Logged with logger.debug(), section skipped
- **Briefing failure**: Sends "📺 Morning briefing failed: {error}" and returns
- **Heartbeat failures**: Logged with logger.debug(), check skipped
- **Health check failures**: Logged with logger.warning(), message sent with all issues

### Critical Failures
- **Auto-rollback**: Triggered if last deploy did not pass verify
- **Git checkout failure**: Sends error message, does not restart
- **No stable commit**: Sends error message, does not rollback

### Timeout Handling
- **PollingManager wait_for()**: 5s timeout per key, continues if timeout
- **No blocking**: Briefing proceeds even if poll times out (may read stale data)

### Startup Recovery
- **Missed briefing**: Detected by checking channel_history for today
- **Recovery**: Sends briefing immediately if missed
- **Edge case**: If briefing fails on recovery, logs error and continues

## 8. Testing Strategy

### Test Coverage
- **scripts/verify.py**: 204/204 tests pass
- **Briefing tests**: morning_briefing runs, output contains all sections
- **Trend tests**: _trend() handles zero, positive, negative, rounding
- **Sleep hours tests**: should_send_now() respects time windows
- **Queue tests**: flush_morning_queue, get_pending_observations, mark_sent
- **Reminder tests**: already_reminded, mark_reminded
- **Polling tests**: wait_for() timeout behavior

### Test Categories
- **Briefing**: morning_briefing runs without error, output sections (channel stats, gmail, personal tasks, weather, weekly focus)
- **Trend**: _trend() zero division, positive/negative, rounding
- **Queue**: queue_observation, get_pending_observations, mark_sent, flush_morning_queue
- **Polling**: record_poll, get_last_poll, get_all_last_polls, wait_for() timeout
- **Rate limits**: api_rate_limits table, api_call_log table, get_api_state, record_call, can_call
- **Deployments**: deploy_history table, get_last_stable_commit, get_last_deploy

### Test Execution
- **Command**: `uv run python scripts/verify.py`
- **Pass criteria**: 204/204 tests pass
- **Deploy gate**: Must pass before GitHub commit

## 9. Related ADRs
- ADR-027: PollingManager Layer (wait_for coordination)
- ADR-030: Deduplication Strategy (queue management)
- ADR-031: Missed Task Push-Forward and Recurrence Recovery (nightly_summary)
