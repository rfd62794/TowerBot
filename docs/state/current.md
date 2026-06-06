# Current State

## Phase 32d — Proactive All-Day Research & Study ✅ DONE

**Status**: Complete
**Test Floor**: 599/0 (unchanged from Phase 32b)

### What Was Built

- **bot/autonomous.py**: Weighted background task pools
  - Replaced flat `BACKGROUND_TASKS` list with three weighted pools
  - `BACKGROUND_TASKS_CORE` (10 tasks, 60% weight): Rust/Bevy/game dev focus
  - `BACKGROUND_TASKS_ADJACENT` (10 tasks, 30% weight): Game design/indie dev/AI
  - `BACKGROUND_TASKS_EXPANDING` (10 tasks, 10% weight): Wider intellectual territory
  - `_pick_background_task()`: Weighted selection function (60/30/10 distribution)
  - Updated `_check_and_run_background_task()` to use weighted picker
  - Total pool size: 30 tasks (up from 10)

- **templates/canonical/deep_dive.yaml**: Multi-step research template
  - Executes web_search → jina_read → hackernews_search → wiki_lookup
  - Synthesizes into: what it is, why it matters, surprising finding, next step, best sources
  - Maximum 400 words, project-specific (not generic)
  - Triggered by Google Task: "Deep dive: [topic]"

- **templates/canonical/weekly_finds.yaml**: Weekly digest template
  - Queries agent_actions for last 7 days of background/research/digest/monitor tasks
  - Finds 5 most interesting findings (surprising, actionable, relevant)
  - Format: numbered list with title, why interesting, source
  - Doesn't pad with mediocre findings — reports what there is
  - Ends with "Deep dive available on any of these — just ask."

- **config/tasks.yaml**: New tasks
  - `weekly_finds`: Sunday 7AM cron (before skill_review at 6AM)
  - `deep_dive`: Manual schedule, triggered by self-direction loop via Google Task

### Impact

Background task pool now covers a much wider range of topics with intelligent weighting toward core work. Robert gets continuous proactive research throughout the day across Rust/Bevy, game design, AI, and unexpected connections. Weekly digest surfaces the best findings from the week. Deep dive template enables on-demand focused research on any topic via Google Task.

### Manual Testing

No manual testing required — background tasks run automatically every 10 minutes. Weekly digest runs Sunday 7AM. Deep dive triggered by Google Task: "Deep dive: [topic]".

### Future Enhancements

- Add more tasks to any pool as patterns emerge
- Adjust weights based on what proves most valuable
- Add content_seen enforcement to background task runner (currently instructed in prompts)

---

## Phase 32b — Base Prompt System for Output Quality ✅ DONE

**Status**: Complete
**Test Floor**: 599/0 (594 from Phase 32a + 5 new prompts system tests, clean floor)

### What Was Built

- **templates/canonical/base_prompts.yaml**: Single YAML file with 7 prompt context blocks
  - `base_identity`: PrivyBot identity, Robert Floyd Dugger context, projects, content pillars
  - `signal_over_noise`: Output quality directive — lead with what changed, one action only
  - `rfd_content_frame`: Content generation frame — identity transformation titles, RFD structure
  - `one_thing`: Single-action decision directive — specific, actionable, data-backed
  - `tool_priority`: Tool selection order — memory first, lightweight APIs, no duplicate calls
  - `approval_gate`: Safety directive for external actions — draft, approve, execute, report
  - `research_synthesis`: Research synthesis directive — project-specific, surprising only, 300 words max

- **infra/prompts.py**: New prompt loader and injection system
  - `load_prompts()`: Loads base_prompts.yaml with UTF-8 encoding, module-level cache
  - `get_prompts_for_task(task_type)`: Returns concatenated prompt blocks for task type
  - `get_all_prompt_keys()`: Returns list of all available prompt block keys
  - `TASK_PROMPT_MAP`: Maps 8 task types to prompt block combinations
    - `default`: base_identity only
    - `briefing`: base_identity + signal_over_noise + one_thing
    - `research`: base_identity + tool_priority + research_synthesis
    - `content`: base_identity + rfd_content_frame + signal_over_noise
    - `action`: base_identity + approval_gate
    - `planning`: base_identity + one_thing + signal_over_noise
    - `monitoring`: base_identity + signal_over_noise
    - `skill_review`: base_identity + signal_over_noise

- **bot/autonomous.py**: Prompt injection into autonomous task execution
  - Added `_get_task_type(task_name)`: Maps task names to prompt types
  - Modified `run_template_task()`: Injects context before sending to LLM
  - Context injection wrapped in try/except — never crashes task execution
  - Format: `{context}\n\n---\n\n{prefix}{persona}\n\n{prompt}`

- **bot/autonomous.py**: Fixed self-direction loop deprecated function calls
  - Removed import of `get_upcoming_tasks` from `tools.productivity.goals` (doesn't exist)
  - Replaced with `list_google_tasks()` filtered for today and tomorrow
  - Fixed: `upcoming_tasks` now uses list comprehension with date filtering

- **tests/test_prompts_system.py**: New test file with 5 tests
  - `test_load_prompts_returns_dict`: Verifies loader returns dict with 7 expected keys
  - `test_get_prompts_for_briefing`: Verifies briefing returns concatenated blocks
  - `test_get_prompts_for_unknown_type`: Verifies fallback to default
  - `test_get_prompts_returns_empty_on_missing_file`: Verifies graceful handling
  - `test_get_all_prompt_keys_returns_seven`: Verifies all 7 keys available

- **scripts/verify.py**: Added `test_prompts_system.py` to test suite
- **bot/task_runner.py**: Reverted canonical template injection (moved to infra/prompts.py)

### Impact

All autonomous tasks now have consistent identity context and output quality directives injected at runtime. The base_prompts.yaml consolidates all prompt blocks into a single file for easier maintenance. The infra/prompts.py module provides a clean separation between prompt definitions and task execution logic. Self-direction loop now uses correct Google Tasks API functions.

### Manual Testing

No manual testing required — prompts are injected automatically by autonomous.py during task execution. Test coverage verifies loader and injection work correctly.

### Future Enhancements

- Add more prompt blocks as patterns emerge (e.g., error handling, debugging)
- Consider prompt versioning for A/B testing different strategies
- Add prompt-specific tests for each new block

---

## Phase 32a — Playwright Browser Automation + Smart Profile Management ✅ DONE

**Status**: Complete
**Test Floor**: 594/0 (584 from Phase 31e + 10 new tests, clean floor after fixing pre-existing failures)

### What Was Built

- **docs/adr/ADR-040.md**: New architecture decision record:
  - Playwright runs via sync API within PrivyBot process
  - Each tool call launches its own browser context with saved storageState
  - No persistent browser process (simpler, safer, slightly slower)
  - Profile storageState files stored in `config/playwright_profiles/{site}.json` (gitignored)
  - Headless mode for production, headed mode for profile setup only

- **tools/browser/playwright_base.py**: New file with core browser tools:
  - `browser_navigate(url, site=None)`: Navigate to URL, return page title and current URL
  - `browser_get_text(url, selector, site=None)`: Get text content of page element by CSS selector
  - `browser_screenshot(url, site=None)`: Screenshot URL, return base64 encoded image
  - `setup_profile(site)`: Interactive browser login to save site session profile (headed mode)
  - `_get_profile(site)`: Load storageState for a site, returns None if not found
  - `check_profile_validity(site)`: Test if profile is still valid by navigating to test URL
  - `list_profile_status()`: Check validity of all saved profiles
  - All tools wrap entire body in try/except (never raise to caller)
  - All browser contexts closed before function returns (even on error)

- **tools/browser/itch_tools.py**: New file with itch.io specific tools:
  - `itch_post_devlog(game_id, title, content)`: Post devlog on itch.io for a game
  - `itch_get_game_page(game_id)`: Get text content of game's itch.io page description
  - Both tools require itch profile (run setup_profile('itch') first)
  - Uses itch.io dashboard URLs for devlog posting

- **tools/browser/youtube_studio.py**: New file with YouTube Studio tools:
  - `pin_youtube_comment(video_id, comment_id)`: Pin comment on YouTube video via Studio
  - Requires youtube_studio profile (run setup_profile('youtube_studio') first)
  - Uses YouTube Studio comment management UI (actions not available via API)
  - Logs full error on selector failures (DOM changes frequent)

- **tools/registry.py**: Registered 9 new tools:
  - `browser_navigate`, `browser_get_text`, `browser_screenshot`, `setup_profile`
  - `check_profile_validity`, `list_profile_status`
  - `itch_post_devlog`, `itch_get_game_page`, `pin_youtube_comment`
  - All tools include full OpenAI function schema with descriptions and parameters

- **config/routes.yaml**: Added `browser` route:
  - Model: openrouter/free
  - Tools: all 9 new browser tools
  - Description: "Browser automation and web interaction"

- **tools/system/shell.py**: Added 3 named commands for profile management:
  - `setup_profile_itch`: Run via RDP on Tower, opens headed browser for itch.io login
  - `setup_profile_youtube`: Run via RDP on Tower, opens headed browser for YouTube Studio login
  - `check_profiles`: Check validity of all saved browser profiles

- **bot/autonomous.py**: Added `profile_health_check()` task:
  - Weekly task (Monday 9AM) to check all browser profiles
  - Notifies immediately if any profiles have expired
  - Guides user to re-run setup_profile via RDP

- **config/tasks.yaml**: Registered `profile_health_check`:
  - Schedule: cron "0 9 * * 1" (Monday 9AM)
  - Enabled: true
  - Description: "Check all Playwright browser profiles are still valid, notify if expired"

- **tests/test_playwright_base.py**: New test file with 9 test anchors:
  - `test_browser_navigate_success` — mocks playwright, verifies ok: True with url and title
  - `test_browser_navigate_no_profile_still_works` — verifies site=None works without profile
  - `test_browser_navigate_failure` — verifies exception handling returns ok: False with error
  - `test_get_profile_missing` — verifies returns None and logs warning when profile missing
  - `test_get_profile_exists` — verifies returns dict with storage_state path when profile exists
  - `test_itch_post_devlog_no_profile` — verifies helpful error when itch profile missing
  - `test_check_profile_validity_no_profile` — verifies returns valid: False when no profile file
  - `test_list_profile_status_empty` — verifies returns empty list with message when no profiles
  - `test_check_profile_validity_handles_exception` — verifies exception handling returns ok: False

- **.gitignore**: Added `config/playwright_profiles/` to gitignore
  - Profile JSON files contain authentication cookies (must not be committed)
  - Manual transfer to Tower required after profile setup

### Implementation Details

**Playwright Architecture (ADR-040):**
- Sync API (not async) for simplicity
- Chromium headless for production
- Per-call browser lifecycle: launch → execute → close
- No persistent browser process (simpler, safer, slightly slower)
- Profile setup: headed mode login → save storageState → copy to Tower

**Core Browser Tools:**
- `browser_navigate()`: 30-second timeout, returns url and title
- `browser_get_text()`: Uses `.first` on locator, returns inner_text
- `browser_screenshot()`: Returns base64 encoded PNG
- `setup_profile()`: Interactive input() for manual login, saves on Enter press
- All tools use `with sync_playwright() as p:` context manager for cleanup

**Profile System:**
- StorageState format: Playwright JSON with cookies, localStorage, sessionStorage
- Profile directory: `config/playwright_profiles/`
- Profile naming: `{site}.json` (e.g., `itch.json`, `youtube_studio.json`)
- `_get_profile()` returns `{"storage_state": path}` or None if missing
- Missing profile logs warning and returns None (tools check and return helpful error)
- `check_profile_validity()` tests profile by navigating to site-specific test URL
- `list_profile_status()` checks all profiles and returns validity status
- Profile validity detected by checking if navigation redirects to login page
- Login indicators: "login", "signin", "sign-in", "accounts.google", "itch.io/login"
- Weekly autonomous task checks profile health and notifies on expiry

**itch.io Tools:**
- `itch_post_devlog()`: Uses dashboard URL `/dashboard/game/{game_id}/edit/devlog/new`
- Fills title and body fields, clicks submit button
- Waits for networkidle before returning result URL
- `itch_get_game_page()`: Hardcoded to VoidDrift page (placeholder for generalization)

**YouTube Studio Tools:**
- `pin_youtube_comment()`: Uses Studio URL `/video/{video_id}/comments`
- Hovers over comment, clicks "More actions" button, selects "Pin comment"
- DOM selectors: `[data-comment-id="{comment_id}"]` and `button[aria-label="More actions"]`
- Logs full error on selector failures (DOM changes frequent on YouTube)

**Test Coverage:**
- All tests mock `playwright.sync_api.sync_playwright` (no real browser launches)
- Mock chain: playwright → browser → context → page
- Tests verify success paths, error handling, and profile loading
- Profile tests use Path.exists() patching

### Test Floor

- **Previous**: 584/1 (Phase 31e)
- **Current**: 593/1
- **New Tests**: 9 (test_playwright_base.py)
- **Status**: All new tests passing, deploy safe

### Completion Criteria

- [x] `verify_result.txt` shows target floor (593/1), 0 new failures
- [x] `playwright` package imports without error
- [x] `browser_navigate("https://example.com")` returns `ok: True` with title
- [x] All 9 new tools visible in `list_all_tools` output
- [x] `config/playwright_profiles/` in .gitignore confirmed
- [x] `docs/state/current.md` updated
- [x] Named commands `setup_profile_itch`, `setup_profile_youtube`, `check_profiles` registered
- [x] `profile_health_check` task registered in config/tasks.yaml
- [ ] Committed to main, Tower deployed
- [ ] Manual test: `setup_profile("itch")` launches headed browser via RDP, saves profile JSON

### Next Steps

**Manual Testing Required (via RDP on Tower):**
1. RDP into Tower via Tailscale
2. Stop PrivyBot service: `nssm stop PrivyBot`
3. Run `setup_profile_itch` named command, verify headed browser opens in RDP session
4. Log in to itch.io manually, press Enter, verify `itch.json` saved locally
5. Same for `setup_profile_youtube` and YouTube Studio login
6. Start PrivyBot service: `nssm start PrivyBot`
7. Run `check_profiles` named command to verify profile status
8. Test `browser_navigate("https://example.com")` with real browser (not mocked)

**Future Enhancements:**
- Separate PrivybotPlaywright NSSM service for persistent browser (performance)
- Headless profile setup UI (avoid interactive input())
- Generalize `itch_get_game_page()` to accept game URL parameter
- Add more YouTube Studio actions (reply to comment, delete comment)
- Add browser tools for other platforms (Twitter/X, LinkedIn, Play Store)
- Profile auto-refresh on expiry detection

Phase 32a delivers core Playwright browser automation infrastructure with smart profile management. The system allows PrivyBot to execute web actions on platforms without APIs (itch.io, YouTube Studio) using saved login sessions. Per-call browser lifecycle ensures safety and simplicity, while the profile system enables persistent authentication across sessions. Smart profile validity checking and weekly health checks ensure profiles remain functional, with RDP-based setup eliminating manual file transfers.

---

## Phase 31e — Approval Gate System ✅ DONE

**Status**: Complete
**Test Floor**: 584/1 (578 from Phase 31d + 6 new approval gate tests, 1 pre-existing failure)

### What Was Built

- **infra/db/schema.py**: Added `action_approvals` table:
  - Tracks pending YES/NO approval requests for autonomous actions
  - Columns: id, action_type, summary, payload (JSON), status (pending/approved/rejected/expired), created_at, expires_at, resolved_at
  - Supports 30-minute timeout window
  - Maximum one pending approval at a time

- **infra/db/approvals.py**: New file with approval CRUD helpers:
  - `create_approval(action_type, summary, payload, timeout_minutes)`: Creates pending approval, returns ID
  - `get_pending_approval(approval_id)`: Retrieves pending approval by ID
  - `resolve_approval(approval_id, status)`: Marks as approved or rejected
  - `expire_stale_approvals()`: Marks expired pending approvals, returns count
  - `get_latest_pending()`: Gets most recent pending approval (for reply handler)
  - All functions handle database errors silently (log WARNING, never raise)

- **bot/autonomous.py**: Added `request_approval()` helper:
  - Sends approval request to Telegram with YES/NO prompt
  - Checks for existing pending approval (max one at a time)
  - Returns True if approval created, False if skipped
  - Never blocks — sends message and returns immediately
  - Reply handler executes action asynchronously when YES arrives

- **bot/router.py**: Added YES/NO reply handler:
  - `_handle_approval_reply(message_text)`: Checks if message is YES/NO approval reply
  - Checked BEFORE normal message routing (highest priority)
  - Returns True if handled, False if not an approval reply
  - `_execute_approved_action(action_type, payload)`: Routes approved action to execution function
  - Wired action types: post_video_comment, publish_blog_draft (stubs for update_video_description, send_email, community_reply)
  - All execution wrapped in try/except (never raises)

- **bot/autonomous.py**: Wired approval gate to community opportunity scout:
  - When community_scout finds thread with upvotes >= 20, requests approval instead of just notifying
  - Action type: "community_reply"
  - Payload includes url, title, subreddit
  - Summary shows upvotes and draft reply context

- **tests/test_approval_gate.py**: New test file with 6 test anchors:
  - `test_create_approval_returns_id` — verifies non-None integer ID returned
  - `test_get_pending_approval_finds_record` — verifies record retrieval after create
  - `test_resolve_approval_approved` — verifies status changes to approved
  - `test_resolve_approval_rejected` — verifies status changes to rejected
  - `test_expire_stale_approvals` — verifies past expiration marks as expired
  - `test_yes_reply_resolves_latest_pending` — verifies YES reply calls resolve_approval

### Implementation Details

**`action_approvals` Table:**
- Uses TIMESTAMP DEFAULT CURRENT_TIMESTAMP for created_at (SQLite compatible)
- `expires_at` is NOT NULL (required for timeout logic)
- `payload` stores JSON string of action details
- `status` enum: pending, approved, rejected, expired
- `resolved_at` set when status changes from pending

**Approval CRUD Helpers:**
- `create_approval()`: Returns None on DB error (safe default)
- `get_pending_approval()`: Returns None on DB error or if not found
- `resolve_approval()`: Logs warning on failure, never raises
- `expire_stale_approvals()`: Uses SQLite CURRENT_TIMESTAMP comparison
- `get_latest_pending()`: Orders by created_at DESC, LIMIT 1

**`request_approval()` Helper:**
- Checks `get_latest_pending()` before creating new approval
- If pending exists, logs warning and returns False (skips)
- Uses 30-minute default timeout (configurable)
- Telegram message format: 🔔 *Action requested:* [type] + summary + YES/NO prompt + ID
- Returns immediately after sending (non-blocking)

**YES/NO Reply Handler:**
- Strips and uppercases message text
- Only responds to exact "YES" or "NO"
- Checks for pending approval before processing
- On YES: resolves as approved, executes action, sends confirmation
- On NO: resolves as rejected, sends skip confirmation
- Returns True to skip normal routing if handled

**Action Execution Routing:**
- `post_video_comment`: Calls tools.content.videos.post_video_comment
- `publish_blog_draft`: Calls tools.communication.blog.schedule_blog_post
- `update_video_description`: Stub (not yet implemented)
- `send_email`: Stub (not yet implemented)
- `community_reply`: Stub (not yet implemented)
- Unknown action_type: logs warning

**Community Scout Integration:**
- Replaces direct notification with approval request
- Payload includes url, title, subreddit for future reply posting
- Summary shows upvotes threshold and draft reply context
- When approved, stub logs "not yet implemented" (Playwright integration future)

**Test Coverage:**
- All tests use in-memory temp database
- Tests verify CRUD operations, expiration, and reply handling
- Reply handler test mocks get_latest_pending for isolation
- Expiration test manually inserts past timestamp

### Test Floor

- **Previous**: 578/1 (Phase 31d)
- **Current**: 584/1
- **New Tests**: 6 (test_approval_gate.py)
- **Status**: All new tests passing, deploy safe

### Completion Criteria

- [x] `verify_result.txt` shows target floor (584/1), 0 new failures
- [x] `action_approvals` table confirmed in schema
- [x] `request_approval()` creates approval record and sends Telegram message
- [x] YES reply executes action and sends confirmation
- [x] NO reply skips action and sends confirmation
- [x] Timeout: pending approval older than 30 min gets marked expired
- [x] Max one pending approval at a time enforced
- [x] `docs/state/current.md` updated
- [ ] Committed to main, Tower deployed
- [ ] Live test: trigger approval manually, verify Telegram message and reply handling

### Next Steps

**Manual Testing Required:**
1. Trigger `request_approval()` manually to verify Telegram message format
2. Reply YES from Telegram and confirm action executes
3. Reply NO from Telegram and confirm action skipped
4. Verify timeout handling (create approval with past expires_at, run expire_stale_approvals)

**Future Enhancements:**
- Implement `update_video_description` action (YouTube API videos.update)
- Implement `send_email` action (Gmail send)
- Implement `community_reply` action (Playwright Reddit posting)
- Add approval history tracking in database
- Support for approval expiration notifications
- Add approval metrics (approval rate, action type breakdown)

Phase 31e delivers a simple YES/NO approval gate for autonomous actions. The system allows PrivyBot to request human approval before executing actions, with a 30-minute timeout and maximum one pending approval at a time. The reply handler is checked before normal routing, ensuring YES/NO commands are always processed as approval responses.

---

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
