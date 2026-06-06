# Current State

## Phase 31a — Morning Briefing Enhancements ✅ DONE

**Status**: Complete
**Test Floor**: 561/2 (554 existing + 7 new briefing tests, 2 pre-existing failures)

### What Was Built

- **bot/scheduler.py**: Added 5 new sections to `morning_briefing()`:
  - Google Tasks due today (via `list_google_tasks()` filtered for today's date)
  - Overnight findings (via `get_overnight_actions()` from agent_actions table)
  - Current platform stats (via `get_itch_stats()` direct API call)
  - Commit digest (via `get_recent_commits()` filtered for last 24 hours)
  - Weekly mirror (Monday only, agent_actions task counts by category)
- **Helper function**: `_hours_ago()` to calculate hours from ISO date strings
- **tests/test_briefing.py**: Added 7 new test anchors:
  - `test_briefing_includes_google_tasks` — verifies Google Tasks section
  - `test_briefing_tasks_empty_ok` — handles empty task lists gracefully
  - `test_briefing_overnight_findings` — surfaces autonomous task results
  - `test_briefing_no_overnight_findings` — handles empty overnight actions
  - `test_briefing_commit_digest` — shows recent commits
  - `test_briefing_weekly_mirror_monday` — Monday-only weekly summary
  - `test_briefing_weekly_mirror_not_monday` — skips on non-Monday days

### Implementation Details

**Google Tasks Section:**
- Uses `list_google_tasks()` from Google Tasks API
- Filters for tasks with `due_date` matching today and `status != "completed"`
- Shows max 5 tasks, skips section if none due today

**Overnight Findings:**
- Queries `agent_actions` table via `get_overnight_actions()` (last 8 hours)
- Shows max 3 findings with task name and result preview (100 chars)
- Skips section if no overnight actions

**Current Platform Stats:**
- Direct call to `get_itch_stats()` for itch.io game metrics
- Shows top 2 games with views and download counts
- Replaces delta metrics (nightly_snapshot stores function call syntax, not JSON)

**Commit Digest:**
- Uses `get_recent_commits()` from GitHub API
- Filters commits from last 24 hours using `_hours_ago()` helper
- Shows max 3 commits with repo name and truncated message (80 chars)

**Weekly Mirror (Monday Only):**
- Fires only on Monday (`weekday() == 0`)
- Queries `agent_actions` for task counts by category over last 7 days
- Shows top 5 task names with execution counts
- Skips silently on non-Monday days

### Test Floor

- **Previous**: 554/2 (pre-existing failures in test_tools_search.py, test_autonomous.py)
- **Current**: 561/2
- **New Tests**: 7 (test_briefing.py)
- **Status**: All new tests passing, deploy safe

### Debt Filed

- **nightly_snapshot JSON output**: Task currently stores function call syntax in result column instead of structured JSON. Fix in `config/tasks.yaml` to output JSON for delta metrics calculation.

### Next Steps

Phase 31a enhances the morning briefing to surface data already being collected by autonomous tasks and external APIs. The briefing now provides a comprehensive daily overview including tasks, overnight findings, platform stats, recent commits, and weekly activity summaries.
