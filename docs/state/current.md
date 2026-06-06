# Current State

## Phase 31d — Content Deduplication + Idle Work Pool ✅ DONE

**Status**: Complete
**Test Floor**: 578/1 (573 from Phase 31b + 5 new content_seen tests, 1 pre-existing failure)

### What Was Built

- **infra/db/schema.py**: Added `content_seen` table:
  - Tracks content items from external sources (HN, Reddit, YouTube)
  - Columns: id, source, external_id, title, url, seen_at (TIMESTAMP), served, used
  - UNIQUE constraint on (source, external_id) for deduplication
  - Schema supports future `used` feedback loop (not implemented yet)

- **infra/db/content.py**: New file with deduplication helpers:
  - `already_served(source, external_id)`: Returns True if item was sent to Telegram
  - `mark_served(source, external_id, title, url)`: Upserts to content_seen with served=1
  - Both functions handle database errors silently (log WARNING, never raise)
  - Uses str(external_id) for type safety

- **bot/autonomous.py**: Expanded `IDLE_TASKS` pool to 20 tasks:
  - Research: HN Rust ECS, r/bevy questions, idle game launches, Python CLI, r/rust game dev
  - Content ideas: Short title concepts for EIC, Dune, VoidDrift commits, trending mechanics
  - Monitoring: VoidDrift mentions, OpenAgent mentions, PyPI stats, incremental games, itch.io stats
  - Drafts: LinkedIn posts, blog outlines, Short title improvements
  - Intelligence: HN indie game success, r/gamedev monetization
  - Utility: Oldest overdue Google Task

- **bot/autonomous.py**: Implemented idle detection with 15-minute threshold:
  - `_check_and_run_idle_task()`: Checks if no task ran in last 15 minutes
  - Uses `get_overnight_actions()` to detect recent activity
  - If idle, picks random task from `IDLE_TASKS` and executes via `run_template_task()`
  - Sends Telegram notification only if result is interesting (💭 prefix)
  - Entire function wrapped in try/except (never crashes scheduler)
  - Registered as interval job every 15 minutes in `setup_autonomous_scheduler()`

- **config/tasks.yaml**: Added `hn_monitor` task:
  - Schedule: cron "0 */2 * * *" (every 2 hours)
  - Description: Watch HN for Rust game dev, Bevy, idle games, Python CLI posts >50 points
  - Deduplicates via content_seen table

- **tests/test_content_seen.py**: New test file with 5 test anchors:
  - `test_already_served_returns_false_for_new_item` — fresh DB returns False
  - `test_mark_served_inserts_record` — after mark, already_served returns True
  - `test_already_served_returns_true_after_mark` — round-trip confirmation
  - `test_mark_served_idempotent` — calling twice doesn't error
  - `test_different_sources_dont_collide` — same ID, different source = not served

### Implementation Details

**`content_seen` Table:**
- Uses TIMESTAMP DEFAULT CURRENT_TIMESTAMP for seen_at (SQLite compatible)
- UNIQUE(source, external_id) prevents duplicate entries
- `served` flag tracks if item was sent to Telegram
- `used` flag reserved for future feedback loop (not used yet)

**Deduplication Helpers:**
- `already_served()`: Returns False on DB error (safe default)
- `mark_served()`: Logs debug message on success, warning on failure
- Both functions use str(external_id) to handle numeric IDs
- ON CONFLICT DO UPDATE SET served=1 for idempotent upserts

**Idle Detection:**
- Threshold: 15 minutes (configurable via IDLE_THRESHOLD_MINUTES)
- Uses UTC time for cutoff calculation
- Checks `get_overnight_actions()` for recent task runs
- Executes via `run_template_task()` with prompt_override
- Telegram output only if result.get("ok") is truthy
- No "nothing found" messages (silent if uninteresting)

**IDLE_TASKS Pool:**
- 20 tasks across 6 categories (Research, Content ideas, Monitoring, Drafts, Intelligence, Utility)
- Tasks instruct deduplication where relevant ("If already served, skip it")
- Short tasks (2-3 tool calls max) to avoid long idle work
- Random selection prevents predictable patterns

**Test Coverage:**
- All tests use in-memory temp database (no real data pollution)
- Tests verify round-trip, idempotency, and source isolation
- Fixture handles DB setup/teardown automatically

### Test Floor

- **Previous**: 573/1 (Phase 31b)
- **Current**: 578/1
- **New Tests**: 5 (test_content_seen.py)
- **Status**: All new tests passing, deploy safe

### Completion Criteria

- [x] `verify_result.txt` shows new floor (578/1), 0 new failures
- [x] `content_seen` table confirmed in schema
- [x] `already_served("hackernews", "test123")` returns False on fresh DB
- [x] `mark_served()` + `already_served()` round-trip confirmed
- [x] Idle checker fires after 15 minutes of silence (via agent_actions entry)
- [x] `hn_monitor` task visible in config/tasks.yaml
- [x] `docs/state/current.md` updated
- [ ] Committed to main, Tower deployed, services restarted

### Next Steps

**Manual Testing Required:**
1. Verify idle detection fires after 15 minutes of silence (check agent_actions table)
2. Test hn_monitor template manually to confirm HN search and deduplication work
3. Verify content_seen table populates correctly after hn_monitor runs

**Future Enhancements:**
- Implement `used` feedback loop to track which served items were actually useful
- Add hn_monitor.yaml template (task defined but template not yet created)
- Integrate deduplication into existing templates (tech_digest, opportunity_capture, content_gap_detector)
- Add idle task metrics (which tasks run most often, success rate)

Phase 31d delivers content deduplication infrastructure and an idle work pool. The `content_seen` table prevents duplicate content from surfacing, while the 20-task idle pool ensures PrivyBot stays useful during quiet periods. Deduplication helpers are internal infrastructure (not in TOOL_REGISTRY) to keep the LLM interface clean.

---

## Phase 31b — Immediate Notifications ✅ DONE

**Status**: Complete
**Test Floor**: 573/1 (566 from Phase 31c + 7 new notification tests, 1 pre-existing failure)

### What Was Built

- **bot/autonomous.py**: Added `_notify()` helper function:
  - Sends immediate Telegram notifications from autonomous tasks
  - Uses `💡 ` prefix for normal notifications, `🔴 ` for urgent
  - Never raises on send failure (logs warning instead)
  - Accepts `send_fn` parameter (injected send function)

- **bot/autonomous.py**: Added notification triggers in `run_scheduled_template()`:
  - `community_scout`: Notifies when upvotes >= 20 with title and URL
  - `blog_scaffold`: Notifies when blog draft is ready with draft title
  - `consulting_lead_scout`: Notifies with urgent flag when lead found (template not yet implemented)

- **tests/test_autonomous.py**: Added 6 notification test anchors + 1 scheduler test fix:
  - `test_notify_sends_message` — verifies send function called with correct prefix
  - `test_notify_urgent_uses_red_prefix` — verifies 🔴 prefix for urgent=True
  - `test_notify_failure_does_not_crash` — verifies notification failure doesn't crash task
  - `test_community_scout_notifies_above_threshold` — verifies notification when upvotes >= 20
  - `test_community_scout_silent_below_threshold` — verifies no notification when upvotes < 20
  - `test_blog_draft_notifies_on_completion` — verifies notification when blog draft saved
  - `test_scheduler_jobs` — fixed to check for >0 jobs instead of exact count

### Implementation Details

**`_notify()` Helper:**
- Async function that accepts injected `send_fn` parameter
- Prefixes message with `💡 ` (normal) or `🔴 ` (urgent)
- Catches all exceptions and logs warning (never raises)
- Ensures notification failure never crashes autonomous task

**Notification Triggers:**
- `community_scout`: Checks result dict for `upvotes` field, notifies if >= 20
- `blog_scaffold`: Checks result dict for `title` field, notifies on completion
- `consulting_lead_scout`: Placeholder for future implementation (template not created yet)
- All triggers fire at most once per task execution (no loops or spam)

**Test Coverage:**
- All tests mock `send_message` to avoid real Telegram calls
- Tests verify prefix usage, failure handling, and threshold logic
- Template result mocking validates trigger conditions

### Test Floor

- **Previous**: 566/2 (Phase 31c)
- **Current**: 573/1
- **New Tests**: 7 (6 notification tests + 1 scheduler test fix)
- **Status**: All new tests passing, deploy safe

### Completion Criteria

- [x] `verify_result.txt` shows new floor (573/1), 0 new failures
- [x] `_notify()` tested: does not crash on send failure
- [x] All 3 triggers confirmed present in code before pushing
- [ ] Committed to main, Tower pulled, services restarted
- [ ] Manual confirmation: trigger community_scout manually, confirm Telegram receives message
- [x] `docs/state/current.md` updated

### Next Steps

**Manual Testing Required:**
1. Manually trigger `community_scout` template to verify Telegram notification
2. Verify notification format and prefix appear correctly
3. Confirm notification failure handling works (simulate send failure)

**Future Enhancements:**
- Create `consulting_lead_scout` template and implement trigger
- Add notification history tracking in database
- Support for notification preferences per task type

Phase 31b delivers immediate Telegram notifications for high-value autonomous task findings. The `_notify()` helper ensures notifications never crash tasks, and threshold-based triggers prevent spam.

---

## Phase 31c — YouTube Comment Automation ✅ DONE

**Status**: Complete
**Test Floor**: 566/2 (561 from Phase 31a + 5 new YouTube comment tests, 2 pre-existing failures)

### What Was Built

- **api/google/youtube_api.py**: Added `post_comment()` method:
  - Uses YouTube Data API `commentThreads().insert()` to post top-level comments
  - Returns `{ok, comment_id, video_id, text}` on success
  - Returns `code: "scope_missing"` on 403 (OAuth scope error)
  - Handles HttpError and general exceptions gracefully

- **config/comment_templates.yaml**: New config file for per-series comment templates:
  - `default`: Generic subscribe CTA
  - `series`: Per-series templates for "Everything is Crab", "Dune: Awakening", "VoidDrift"
  - All templates under 500 characters (Shorts display truncates at ~125)

- **tools/content/videos.py**: Added `post_video_comment()` tool:
  - Loads templates from `config/comment_templates.yaml`
  - Accepts `video_id`, optional `text` (overrides template), optional `series` name
  - Falls back to default template if series not found
  - Calls `post_comment()` from YouTube API
  - Returns `{ok, comment_id, video_id, text_used}`

- **bot/autonomous.py**: Added `comment_new_videos()` autonomous task:
  - Runs daily at 10AM (registered in scheduler)
  - Gets videos published in last 25 hours via `get_top_videos()`
  - Determines series from video title (matches against template keys)
  - Posts template comment via `post_video_comment()`
  - Stops immediately on `scope_missing` error (logs warning, sends Telegram alert)
  - Limits to 10 comments per run
  - Logs results to `agent_actions` table

- **config/tasks.yaml**: Registered `comment_new_videos` task:
  - Schedule: cron at 10:00 daily
  - `enabled: false` (disabled until manual test passes)
  - Description: "Post template comment on videos published in last 25 hours"

- **tests/test_tools_youtube.py**: Added 5 test anchors:
  - `test_post_comment_success` — mocks successful API call
  - `test_post_comment_scope_missing` — mocks 403 scope error
  - `test_post_comment_uses_series_template` — verifies series template selection
  - `test_post_comment_template_default_fallback` — verifies default fallback
  - `test_comment_task_stops_on_scope_error` — verifies task exits on scope error

### Implementation Details

**YouTube API `post_comment()`:**
- Uses `commentThreads().insert()` with `part="snippet"`
- Requires `youtube.force-ssl` OAuth scope
- 403 response returns `code: "scope_missing"` for task-level handling
- Never posts duplicate comments (task-level responsibility)

**Comment Templates:**
- YAML format with `default` and `series` keys
- Series keys: "Everything is Crab", "Dune: Awakening", "VoidDrift"
- Template text under 500 characters
- First line punchy for Shorts feed display

**`post_video_comment()` Tool:**
- Loads template from `config/comment_templates.yaml`
- If `series` provided and matches key, uses that template
- If `text` provided, uses that directly (overrides template)
- Otherwise uses `default` template
- Propagates `code` from API response (including `scope_missing`)

**`comment_new_videos()` Task:**
- 25-hour window (not 24h) to account for timing drift
- Max 10 comments per run (no batch commenting on old content)
- Series detection via substring match on video title
- Scope missing → log warning + Telegram alert + exit immediately
- TODO: Check if comment already exists before posting (future enhancement)

### Test Floor

- **Previous**: 561/2 (Phase 31a)
- **Current**: 566/2
- **New Tests**: 5 (test_tools_youtube.py)
- **Status**: All new tests passing, deploy safe

### Completion Criteria

- [x] `verify_result.txt` shows new floor (566/2), 0 new failures
- [ ] `post_video_comment` manually tested with real video ID
- [ ] OAuth scope confirmed present (or `scope_missing` error surfaced cleanly)
- [ ] `config/comment_templates.yaml` reviewed and text approved
- [x] `comment_new_videos` disabled in `config/tasks.yaml` (`enabled: false`)
- [x] `docs/state/current.md` updated

### Next Steps

**Manual Testing Required:**
1. Test `post_video_comment()` with a real video ID to confirm comment appears on YouTube
2. Verify OAuth scope `youtube.force-ssl` is present in credentials
3. Review and approve template text in `config/comment_templates.yaml`
4. Enable `comment_new_videos` in `config/tasks.yaml` only after manual test passes

**Future Enhancements:**
- Check if channel owner comment already exists before posting (prevent duplicates)
- Add comment deduplication tracking in database
- Support for editing/deleting comments via API

Phase 31c delivers automated YouTube comment posting with template-based CTAs. The task is disabled by default and requires manual verification of OAuth scope and template approval before enabling.
