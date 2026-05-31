# Idle Fallback Task System

## Purpose

Tasks that find nothing should still produce something. Consecutive empty runs are wasted quota and wasted opportunity. This system detects when autonomous tasks return empty results and triggers micro-tasks that produce compounding value.

## Architecture

### Two-Layer System

**Layer 1 — Fallback Task Pool**

A list of micro-tasks that produce small but useful work when main tasks find nothing.

**Layer 2 — Detection Logic**

Logic in `run_autonomous_task()` that detects empty results and triggers fallback tasks after consecutive empty runs.

## Fallback Task Pool

```python
FALLBACK_TASKS = [
    (
        "Pick one post topic from the content inventory (memory: 'Content pipeline'). "
        "Write Question 1 of the five-question extraction — the specific scene prompt. "
        "Save as memory 'Q1 ready: [topic]'."
    ),
    (
        "Find one stale memory (check timestamps on any memory with data that changes). "
        "Refresh it using available tools. Update the memory with fresh value + date."
    ),
    (
        "Look at this week's commit log and itch.io stats. "
        "Find one correlation — did a commit date match a download spike? "
        "Save as memory 'Weekly insight: [date]'."
    ),
    (
        "Read the ROADMAP next steps. Pick the smallest incomplete item. "
        "Write a one-paragraph explanation of why it's next and what blocks it. "
        "Save as memory 'Next build context: [item]'."
    ),
    (
        "Check if blog_structure_generator has a pending draft waiting. "
        "If yes: read it and add one specific scene suggestion to improve Question 1. "
        "If no: generate a hook sentence for the next post topic in the queue."
    ),
]
```

## Detection Logic

### In `bot/autonomous.py`

```python
async def run_autonomous_task(task_name: str, send_fn):
    """
    Execute a single autonomous task with fallback for empty results.
    """
    task = TASKS.get(task_name)
    if not task:
        logger.error(f"Unknown task: {task_name}")
        return

    if not task.get("enabled"):
        logger.debug(f"Task disabled: {task_name}")
        return

    prefix = (
        "[AUTONOMOUS MODE — Robert is not present. "
        "Take action directly. Do not ask clarifying questions. "
        "Never delete data, never send emails. "
        "Begin summary with URGENT: or DONE:]\n\n"
    )

    start = time.time()
    result = ""
    urgent = 0

    try:
        result = await respond(
            prefix + task["prompt"],
            thread_id=f"autonomous_{task_name}"
        )
        duration_ms = int((time.time() - start) * 1000)

        # Check if result is urgent
        if result.upper().startswith("URGENT:"):
            urgent = 1

        record_agent_action(task_name, result, duration_ms, urgent)
        logger.info(f"Task {task_name} completed in {duration_ms}ms")

        # Fallback: if task found nothing useful, run a micro-task
        nothing_phrases = [
            "0 found", "0 mentions", "nothing important",
            "no urgent", "no changes", "no new", "no results"
        ]
        if any(p in result.lower() for p in nothing_phrases):
            consecutive = _count_consecutive_empty_runs(task_name, hours=8)
            if consecutive >= 2:
                fallback_prompt = random.choice(FALLBACK_TASKS)
                fallback_result = await respond(
                    f"[MICRO-TASK — nothing found in {task_name}]\n\n{fallback_prompt}",
                    thread_id="autonomous_fallback"  # shared fallback thread
                )
                record_agent_action(f"fallback_{task_name}", fallback_result, duration_ms, 0)
                logger.info(f"Fallback task triggered after {consecutive} empty runs")

        # Send urgent notification via Telegram
        if urgent:
            await send_fn(f"🚨 {task_name}:\n{result[:500]}")

    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        error_msg = f"ERROR: {str(e)}"
        record_agent_action(task_name, error_msg, duration_ms, 0)
        logger.error(f"Task {task_name} failed: {e}")


def _count_consecutive_empty_runs(task_name: str, hours: int) -> int:
    """
    Count consecutive empty runs for a task within the time window.
    """
    from infra.db import get_db
    from datetime import datetime, timedelta
    
    db = get_db()
    cursor = db.cursor()
    
    cutoff = datetime.now() - timedelta(hours=hours)
    
    cursor.execute("""
        SELECT result FROM agent_actions
        WHERE task_name = ?
        AND created_at > ?
        ORDER BY created_at DESC
    """, (task_name, cutoff))
    
    rows = cursor.fetchall()
    consecutive = 0
    
    nothing_phrases = [
        "0 found", "0 mentions", "nothing important",
        "no urgent", "no changes", "no new", "no results"
    ]
    
    for row in rows:
        result = row[0]
        if any(p in result.lower() for p in nothing_phrases):
            consecutive += 1
        else:
            break
    
    return consecutive
```

## Compounding Effect

Each fallback action is small but compounds over time:

- **Q1 ready** → becomes extraction → becomes draft → becomes published post
- **Stale memory refreshed** → keeps data current without manual intervention
- **Weekly insight** → builds data for marketing decisions
- **Next build context** → reduces friction when returning to stalled projects
- **Blog hook** → accelerates content creation

**Example:**
Across a week of empty `itch_reddit_check` runs (every 30min = 336 runs), you get 5-6 post topics with Question 1 already written, waiting for your voice.

## Threshold Tuning

**Current threshold:** 2 consecutive empty runs within 8 hours

**Rationale:**
- Prevents fallback from triggering on occasional empty results
- 8-hour window catches patterns without being too sensitive
- 2 consecutive runs ensures it's a pattern, not noise

**Adjustable parameters:**
- `hours` — time window for counting consecutive empties
- `consecutive >= 2` — threshold for triggering fallback
- `nothing_phrases` — phrases that indicate empty result

## Thread Management

Fallback tasks use a shared thread: `autonomous_fallback`

**Benefits:**
- Keeps fallback work separate from main task context
- Agent can see history of fallback work
- Easier to audit fallback productivity

## Monitoring

### Tracking Fallback Effectiveness

Add to morning briefing:

```python
def get_fallback_stats() -> dict:
    """Get stats on fallback task execution."""
    from infra.db import get_db
    from datetime import datetime, timedelta
    
    db = get_db()
    cursor = db.cursor()
    
    cutoff = datetime.now() - timedelta(days=1)
    
    cursor.execute("""
        SELECT COUNT(*), AVG(duration_ms)
        FROM agent_actions
        WHERE task_name LIKE 'fallback_%'
        AND created_at > ?
    """, (cutoff,))
    
    count, avg_duration = cursor.fetchone()
    
    return {
        "fallback_runs_24h": count,
        "avg_duration_ms": avg_duration
    }
```

### Morning Briefing Addition

```
🔄 Fallback tasks (last 24h): 5 runs
   - Q1 ready: "How I Ship Directives That Agents Follow"
   - Stale memory refreshed: "OpenAgent stats"
   - Weekly insight: May 12 download spike correlated with Reddit post
```

## Build Estimate

- Implement `_count_consecutive_empty_runs()`: 15 minutes
- Add fallback logic to `run_autonomous_task()`: 15 minutes
- Define FALLBACK_TASKS list: 10 minutes
- Add fallback stats to morning briefing: 20 minutes
- Test with mock empty results: 20 minutes
- **Total: ~80 minutes**

## Priority

**High** — The fallback system will run thousands of times over the bot's lifetime. Worth being deliberate about the fallback task list before committing it.

## Dependencies

- None — uses existing `agent_actions` table
- Optional: fallback stats for morning briefing

## Future Enhancements

1. **Weighted fallback selection** — prioritize tasks based on recent success rate
2. **Task-specific fallbacks** — different fallback pools for different task types
3. **Fallback result tracking** — measure which fallback tasks produce the most value
4. **Adaptive threshold** — adjust consecutive threshold based on task patterns
