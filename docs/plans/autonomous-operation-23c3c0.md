# Basic Autonomous Operation — APScheduler + Task Runner

Implement autonomous task execution using APScheduler, allowing the agent to take scheduled actions without user presence. The agent will run predefined tasks (email triage, nightly snapshot, itch/reddit monitoring) with persistent threads, shared memory, and action logging.

## Files to Create/Modify

**New files:**
- `bot/autonomous.py` — Task definitions, runner, APScheduler setup
- `infra/db/autonomous.py` — DB functions for agent_actions table
- `tests/test_autonomous.py` — DB + scheduler tests

**Modify:**
- `infra/db/schema.py` — Add agent_actions table migration
- `infra/db/__init__.py` — Export new DB functions
- `bot/scheduler.py` — Add overnight actions section to morning_briefing()
- `privybot.py` — Start APScheduler alongside existing loop
- `pyproject.toml` — Add apscheduler>=3.10.4 dependency

## Implementation Details

### bot/autonomous.py
- **TASKS dict**: 3 tasks (email_triage, nightly_snapshot, itch_reddit_check)
- **run_autonomous_task(task_name, send_fn)**:
  - Prefix with autonomous mode instructions
  - Call agent.respond() with thread_id=f"autonomous_{task_name}"
  - Record action to DB with duration_ms
  - Send Telegram if result starts with "URGENT:"
- **setup_autonomous_scheduler(ap_scheduler, send_fn)**:
  - Register interval jobs (email_triage: 120min, itch_reddit_check: 30min)
  - Register cron job (nightly_snapshot: 23:30)
  - max_instances=1 to prevent overlapping runs

### infra/db/schema.py migration
Add to _run_migrations():
```sql
CREATE TABLE IF NOT EXISTS agent_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL,
    ran_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
    result TEXT,
    duration_ms INTEGER,
    urgent INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_agent_actions_ran
    ON agent_actions(task_name, ran_at DESC);
```

### infra/db/autonomous.py
- **record_agent_action(task_name, result, duration_ms)**: INSERT with urgent=1 if result starts with "URGENT:"
- **get_overnight_actions()**: SELECT from last 8 hours, ORDER BY ran_at DESC

### bot/scheduler.py
Add to morning_briefing() after overnight queue flush:
- Call get_overnight_actions()
- Format section with 🤖 emoji
- Show up to 5 actions, prefix 🚨 for urgent

### privybot.py
- Import AsyncIOScheduler, setup_autonomous_scheduler
- Create scheduler with timezone="America/New_York"
- Call setup_autonomous_scheduler() in post_init hook
- scheduler.start() after app.build()
- scheduler.shutdown(wait=False) on shutdown (add cleanup handler)

### pyproject.toml
Add: `apscheduler>=3.10.4`

## Key Design Decisions

- **Thread persistence**: Each task uses persistent thread_id (autonomous_{task_name}) for continuity
- **Memory access**: Shared with user conversations (same memory pool, same tools)
- **Error handling**: try/except → record ERROR in agent_actions → wait for next interval (no retry)
- **Task control**: enabled flag in TASKS dict only (/autonomous command deferred)
- **No agent.py changes**: Use existing agent.respond() with different thread_id and prefix

## Testing

### tests/test_autonomous.py
- ✓ agent_actions table exists
- ✓ idx_agent_actions_ran index exists
- ✓ record_agent_action creates entry
- ✓ get_overnight_actions returns entries from last 8h
- ✓ get_overnight_actions excludes entries older than 8h
- ✓ urgent=1 when result starts with URGENT:
- ✓ setup_autonomous_scheduler registers 3 jobs
- ✓ TASKS dict has 3 enabled tasks

## Field Test (after commit)

```bash
uv run python -c "
from dotenv import load_dotenv; load_dotenv()
from infra.db import init_db; init_db()
from bot.autonomous import run_autonomous_task
import asyncio
async def test():
    await run_autonomous_task('itch_reddit_check', print)
asyncio.run(test())
"
```

Verify: result logged, agent called tools, output is DONE: or URGENT:

## Success Criteria

- 228 + 8 = 236/236 tests pass
- ap_scheduler starts without error
- 3 autonomous jobs registered
- morning_briefing() has overnight actions section
- Field test shows autonomous agent execution
