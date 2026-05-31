# Autonomous Synthesis and Creation Tasks

## Context

Current autonomous tasks are all **monitoring** — they observe and flag. The gap is **synthesis and creation**: finding things you didn't know to look for, producing things you'd have to make yourself.

## Three Categories of Interesting Tasks

### 1. Synthesis — Connecting Data Sources for Non-Obvious Insight

**content_code_gap_analyzer** — 3AM daily
- Cross-references recent commits with YouTube content library
- Identifies missing content opportunities based on development activity
- Example: "You've been building VoidDrift Phase 5 for 3 weeks — no video exists about the Production Tree viewport. 121.8% retention on your last dev log suggests this is your highest-ROI video right now."
- Drafts specific video topic

**itch_cause_finder** — weekly
- Correlates itch.io download spikes with Reddit posts, YouTube uploads, and commit activity
- Finds what actually causes downloads (not intuition, but data)
- Example: "Downloads spiked 3x on May 12. You posted to r/incremental_games on May 11."

**commit_velocity_sentinel** — daily
- Tracks commits per day by repo
- When velocity drops below threshold for 3+ days, reads ROADMAP for that project
- Identifies specific next task and drafts "what would unblock me on X today?" briefing item
- Not a guilt trip — a concrete re-entry point

### 2. Creation — Producing First-Pass Work

**voidrift_devlog_outline** — every 2 weeks
- Pulls latest VoidDrift commits, reads ROADMAP phase status
- Looks at what changed since last video
- Generates structured devlog outline: hook moment, what was built, why it matters to player, what's next
- Saves 2 hours of planning

**rfditservices_post_draft** — Sunday 2AM
- Reads that week's commits, itch stats, YouTube performance, OpenAgent downloads
- Writes blog post skeleton in RFD Content Frame (MOMENT → SURPRISE → STRUGGLE → LESSON → NEXT)
- Robert wakes up Monday with the structure — just needs the authentic voice

**openagent_patch_notes** — when new commits detected
- When `get_recent_commits` finds commits to OpenAgent repo
- Drafts release notes + LinkedIn post draft
- Example: "Shipped v0.2.3: fixed DocumentationAgent abstract class bug. Here's what broke and how I fixed it."
- Every fix becomes a content moment

### 3. Self-Optimization — PrivyBot Improving Itself

**task_output_reviewer** — Sunday 4AM
- Reads last 7 days of `agent_actions`
- For each task: did it find anything actionable? Did URGENT fire? Did proposed actions get acted on?
- Tasks that produce nothing for 2 weeks get flagged for disabling or prompt adjustment
- PrivyBot audits its own usefulness

**quota_pattern_analyzer** — weekly
- Reads `openrouter_usage` (once budget tracking is built)
- Which tasks consume the most quota? Which produce the highest value?
- Proposes task interval adjustments that preserve value while cut cost

## Architectural Upgrade: Event-Driven Tasks

Current tasks run on schedule regardless of conditions. The interesting stuff happens when tasks fire only when conditions are met.

### Proposed Pattern

```python
# Task fires only when condition is met
"itch_cause_finder": {
    "trigger": "when itch_stats shows >20% spike vs 7-day avg",
    "prompt": "Downloads spiked. Find what caused it..."
}

"voidrift_devlog_outline": {
    "trigger": "when VoidDrift commits > 15 in last 14 days",
    "prompt": "Enough has been built. Draft a devlog..."
}
```

### Implementation

PollingManager already checks RateLimitManager before firing. The same pattern extends to business logic conditions:
- Check condition before firing task
- Fire task only if condition is true
- One architectural addition to APScheduler's job model

## Quick Wins (Buildable Tonight)

**commit_velocity_sentinel** — 20 minutes
- Uses `get_recent_commits` (exists)
- Uses `read_local_file(ROADMAP)` (exists)
- Simple threshold logic
- Immediate value: prevents project stalls

**rfditservices_post_draft** — 15 minutes
- Uses existing tools (commits, itch stats, YouTube, OpenAgent)
- Saves output to memory
- RFD Content Frame is known structure
- Immediate value: Monday morning content skeleton

## Data Sources Required

- `get_recent_commits` — exists
- `read_local_file` — exists
- `itch_stats` — exists
- YouTube channel data — exists
- `agent_actions` table — exists
- `openrouter_usage` — needs budget tracking (future)

## Priority

1. **commit_velocity_sentinel** — highest ROI, prevents stalls
2. **rfditservices_post_draft** — content automation, saves time
3. **content_code_gap_analyzer** — content optimization
4. **itch_cause_finder** — marketing insight
5. **task_output_reviewer** — self-optimization
6. **voidrift_devlog_outline** — content automation
7. **openagent_patch_notes** — content automation
8. **quota_pattern_analyzer** — cost optimization (requires budget tracking first)

## Event-Driven Architecture

Requires extending `bot/autonomous.py` TASKS schema:

```python
TASKS = {
    "task_name": {
        "schedule_type": "cron" | "interval" | "event",
        "trigger_condition": lambda: bool,  # for event type
        "hour": int,  # for cron
        "interval_minutes": int,  # for interval
        "enabled": bool,
        "prompt": str,
    }
}
```

PollingManager would check `trigger_condition` before calling `run_autonomous_task`.
