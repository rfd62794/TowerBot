# PrivyBot — Current State

## Phase
Phase 29 — ADR-038 Phase 2: Migration + Drop Tables

## Completed
- Phase 19: Chain System Foundation (ADR-037 + Schema)
  - ADR-037.md: Six primitive architecture locked
  - 5 new SQLite tables: chains, chain_steps, chain_payloads, pattern_candidates, approval_listeners
  - infra/db/chains.py: Chain and step CRUD
  - infra/db/payloads.py: Payload CRUD with JSON serialization
  - templates/canonical/ and templates/experimental/ directories created
  - 15 new tests in test_chain_schema.py
  - Test floor: 379 passed, 0 failed

- Phase 20a: Chain Runner + Step Execution
  - infra/chain/runner.py: ChainRunner with injected dependencies
  - infra/chain/steps.py: 6 step handlers + StepError + StepSkipped
  - infra/chain/__init__.py: package init
  - 20 new tests in test_chain_runner.py
  - Test floor: 399 passed, 0 failed

- Phase 20b: Approval Step + Telegram Reply Router
  - infra/chain/approval.py: Approval listener CRUD + message building
  - infra/chain/steps.py: Real approval_wait handler (creates listener, calls send_fn)
  - bot/approval_router.py: Callback parser + handler
  - bot/transport.py: handle_callback_query async handler
  - privybot.py: CallbackQueryHandler registration
  - 18 new tests in test_approval.py
  - Test floor: 417 passed, 0 failed

- Phase 20c: Observer + Digest + First Template + Production Wiring
  - templates/canonical/hourly_fact.yaml: First canonical template (3 steps)
  - infra/chain/template_loader.py: YAML loading + validation
  - infra/chain/observer.py: Pattern observation logic
  - bot/autonomous.py: Observer job (30min) + weekly digest (Sunday 08:00)
  - bot/approval_router.py: resume_chain_fn wired to real ChainRunner
  - 20 new tests in test_phase20c.py
  - Test floor: 437 passed, 0 failed

- Phase 21: Model Roles + Pydantic + Reasoning
  - infra/chain/schemas.py: Pydantic payload schemas (BasePayload, TextDraftPayload, DataStatsPayload, etc.)
  - infra/db/payloads.py: Pydantic validation on create_payload with fallback to raw dict
  - infra/db/budget_tracking.py: Added get_warning_sent_today() and mark_warning_sent()
  - infra/db/budget_tracking.py: Made record_cost daily_cap_usd optional with registry fallback
  - config/model_registry.yaml: Model capability registry with 8 models, 8 roles, budget caps
  - infra/model_router.py: Role-based model router with budget awareness and spend tracking
  - infra/chain/steps.py: Added StepLoopBack exception, handle_agent_step(), handle_loop_back()
  - infra/chain/runner.py: Handle StepLoopBack with anchor step reset, route llm_call through model router
  - bot/router.py: Added budget spend to /status output
  - 24 new tests in test_phase21.py
  - Test floor: 497 passed, 0 failed

- Phase 22: Director Tools — Full Operational Access
  - tools/meta/director.py: 13 new tools for Claude (chains, templates, memories, DB inspection)
  - Chain tools: get_chains, get_chain, get_chain_payload, start_chain, cancel_chain, resume_chain
  - Template tools: list_templates, get_template, write_template, delete_experimental_template
  - Memory tools: list_memories, delete_memory
  - Pattern tools: get_promotion_candidates
  - DB inspection: query_db (SELECT-only)
  - Hard boundary: write_template and delete_experimental_template cannot touch canonical/
  - All 13 tools registered in TOOL_REGISTRY and exposed via MCP
  - 22 new tests in test_director_tools.py
  - Test floor: 519 passed, 0 failed

- Phase 23: Tool Discovery + Dynamic Registration
  - infra/db/schema.py: Added experimental_tools table for dynamic tool registry
  - tools/meta/tool_registry.py: 4 new tools (a2a_search, register_tool_from_spec, list_experimental_tools, promote_tool)
  - a2a_search: Search a2asearch.com index for MCP tools and skills with fallback URL
  - register_tool_from_spec: Fetch OpenAPI spec, generate tool definitions, register to experimental_tools table
  - list_experimental_tools: List dynamically registered tools with status filter
  - promote_tool: Promote experimental tool to promoted status (explicit call only, no auto-promotion)
  - All 4 tools registered in TOOL_REGISTRY and auto-exposed via MCP
  - 18 new tests in test_tool_registry.py
  - Test floor: 537 passed, 0 failed

- Phase 24: Model Router Wiring + Tool Index
  - config/task_types.yaml: Added model_role field to all 5 TaskTypes (monitor, reporter, creator, planner, chat)
  - Model role mappings: monitor→fast_intent (Groq), reporter→long_context (Gemini Flash), creator→long_context (Gemini Flash), planner→reasoning (DeepSeek), chat→chat (Gemini Flash)
  - config/model_registry.yaml: Updated groq_llama_3_1_70b and gemini_flash to use direct providers (groq, google) instead of openrouter
  - bot/model_helpers.py: Added provider-specific call functions (call_groq, call_gemini, call_openrouter) and get_call_fn(provider)
  - bot/autonomous.py: Wired model_router into run_autonomous_task() and process_delegation_queue()
  - Autonomous tasks now route through model_router based on task_type's model_role
  - infra/model_router.py: Updated route() to use get_call_fn(provider) for provider-specific API calls
  - tools/meta/tool_index.py: 3 new tools (search_tools, list_all_tools, get_tool_info)
  - search_tools: Fast fuzzy search of all registered tools by name and description
  - list_all_tools: List all tools with optional prefix filter
  - get_tool_info: Get full information about a specific tool by exact name
  - All 3 tool index tools registered in TOOL_REGISTRY and auto-exposed via MCP
  - config/routes.yaml: Added 3 tool index tools to system route with trigger phrases
  - 11 new tests in test_model_wiring.py
  - Test floor: 548 passed, 0 failed

- Phase 25: Self-Direction Loop
  - bot/autonomous.py: Added self_direction_loop() function for daily autonomous task planning
  - Reads current state via read_current_state(), get_tasks_today(), get_upcoming_tasks(), get_inbox_summary(), get_itch_stats(), get_blog_posts()
  - Uses model_router with reasoning role to identify 3 highest-value tasks for the day
  - Queues each task via delegation_tools.queue_task() with task_name="self_direction"
  - Saves plan as memory with key='autonomous_plan_{date}' in project layer
  - APScheduler job registered to fire daily at 07:00 with id='self_direction'
  - Sends Telegram notification on completion with task count
  - Autonomous self-direction achieved — Tower now plans its own work

- Phase 26: WordPress Pages Tools
  - api/web/wordpress_api.py: Added get_pages, get_page, update_page, create_page, delete_page methods
  - tools/communication/blog.py: Added 5 page tool wrappers (get_pages, get_page, update_page, create_page, delete_page)
  - tools/registry.py: Registered 5 new page tools with full definitions
  - infra/mcp/config.py: 5 new tools auto-exposed via MCP (uses TOOL_REGISTRY keys)
  - config/routes.yaml: Added 5 page tools to blog route
  - update_page preserves status unless explicitly provided (status=None → no change)
  - create_page defaults to status='draft' (never publish without explicit status='publish')
  - delete_page permanently removes a page (DO NOT CALL without prior approval_wait step)
  - DO NOT CALL notes in docstrings guide Tower's autonomous decision-making
  - tests/test_wordpress_pages.py: 11 new tests covering all page operations
  - scripts/verify.py: Added test_wordpress_pages.py to TEST_FILES
  - Test floor: 559 passed, 0 failed (548 + 11)

## Post-Phase 26: Housekeeping + Google Tasks Tests
- tools/meta/admin.py: Fixed cursor indexing bug in run_diagnostic (lines 116, 127, 136) - now calls .fetchone() before indexing
- tools/meta/director.py: Fixed false-positive CREATE keyword blocking in query_db (line 434) - now uses word-boundary regex
- tests/test_admin_tools.py: Added 3 regression tests (run_diagnostic_queue_depth_numeric, query_db_created_at_not_blocked, query_db_create_table_still_blocked)
- tests/test_google_tasks.py: Created new test file with 14 unit tests for Google Tasks tools (list_google_tasks, get_google_task, create_google_task, update_google_task, complete_google_task, delete_google_task, sync_google_tasks)
- scripts/verify.py: Added test_google_tasks.py to TEST_FILES
- Test floor: 576 passed, 0 failed (559 + 3 + 14)

## Phase 27: Template Scheduler
- bot/autonomous.py: Added run_scheduled_template() function to execute templates via ChainRunner
- bot/autonomous.py: Added setup_template_scheduler() function to register template-based scheduled jobs
- bot/autonomous.py: Integrated template scheduler into setup_autonomous_scheduler()
- bot/autonomous.py: Templates with trigger.schedule config now auto-register APScheduler jobs
- bot/autonomous.py: Supports interval (minutes) and cron (hour, minute, day_of_week) triggers
- bot/autonomous.py: Respects stop_after_hour config to limit template execution hours
- tests/test_autonomous.py: Added 3 tests for template scheduler (registers jobs, skips non-schedule, loads and creates chain)
- Test floor: 579 passed, 0 failed (576 + 3)

## Phase 28: ADR-038 Phase 1 Deprecation
- docs/adr/ADR-038.md: Status changed from Proposed to Accepted
- infra/db/schema.py: Added DEPRECATED comments above tasks and personal_tasks table definitions
- infra/db/goals.py: Added deprecation warnings to 7 functions (get_tasks, get_task, get_tasks_due_today, get_upcoming_scheduled, get_unsynced_tasks, get_tasks_completed_since, get_tasks_with_google_id)
- infra/db/personal_tasks.py: Added deprecation warnings to 6 functions (add_personal_task, get_personal_tasks, get_tasks_due_soon, complete_personal_task, snooze_personal_task, delete_personal_task)
- .windsurf/rules.md: Added ADR-038 stop rule for deprecated task tables
- Inventory report: tasks table has 6 rows, personal_tasks table has 21 rows (all have google_task_id synced)
- Test floor: 579 passed, 0 failed (no new tests - deprecation warnings don't require test coverage)

## Phase 29: ADR-038 Phase 2: Migration + Drop Tables
- infra/db/schema.py: Dropped tasks and personal_tasks table definitions; added task_notifications table for Google Tasks notification deduplication
- infra/db/goals_milestones.py: Created new module for goals and milestones CRUD (separated from deprecated tasks table)
- infra/db/commitments_weekly.py: Created new module for commitments and weekly plans CRUD
- infra/db/__init__.py: Updated imports to use new modules; removed deprecated goals.py and personal_tasks.py re-exports
- tools/productivity/utils.py: Created new module with parse_natural_deadline and parse_recurrence utility functions (migrated from personal.py)
- tools/productivity/goals.py: Refactored to remove deprecated task functions (get_tasks_today, get_upcoming_tasks, add_new_task, update_task); now only handles goals, milestones, commitments, weekly plans
- tools/productivity/__init__.py: Removed imports of deprecated task functions and personal task functions; removed sync import
- tools/productivity/personal.py: Deleted (utility functions migrated to utils.py, DB functions deprecated)
- tools/productivity/sync.py: Deleted (all functions depended on deprecated local task tables)
- tools/registry.py: Removed tool definitions for deprecated task functions (get_tasks_today, get_upcoming_tasks, update_task, add_task) and personal task functions (add_personal_task, list_personal_tasks, complete_personal_task, snooze_personal_task, delete_personal_task)
- bot/router.py: Removed imports of deprecated task functions; updated handle_tasks, handle_task_done, handle_todo, handle_sync to return deprecation messages
- bot/scheduler.py: Removed imports of deprecated task functions (get_upcoming_scheduled, get_tasks_due_today, get_current_weekly_plan); replaced Check 9 with Google Tasks API logic using task_notifications table; removed Check 4 (scheduled tasks reminder)
- infra/polling.py: Removed google_tasks polling registration (run_sync function deleted)
- scripts/cleanup_test_data.py: Removed references to personal_tasks table and get_personal_tasks function
- conftest.py: Removed add_commitment import from deleted infra.db.goals
- tests/test_personal_tasks.py: Deleted (tests for deprecated functionality)
- tests/test_google_tasks_sync.py: Deleted (tests for deleted sync module)
- tests/test_tools_goals.py: Removed tests for deprecated task functions (test_get_tasks_today, test_get_upcoming_tasks, test_add_new_task, test_update_task)
- tests/test_google_tasks.py: Removed tests for sync_google_tasks functions
- tests/test_polling.py: Updated test_register_defaults to expect 4 registered keys (down from 5 after removing google_tasks)
- tests/test_db.py: Removed test_task_roundtrip (deprecated task functions); added tests for task_notifications, task_reminders, commitments tables; added test_deprecated_tables_removed with cleanup logic
- tests/test_utils.py: Created new test file with unit tests for parse_natural_deadline and parse_recurrence functions
- tests/test_scheduler.py: Created new test file with tests for Google Tasks overdue check deduplication, calendar alert mechanism, and nightly_summary no-op
- Test floor: 551 passed, 0 failed, 2 missing (test_personal_tasks.py, test_google_tasks_sync.py intentionally deleted)

## Next
Phase 30 — TBD

---

## Admin Tools (Post-Phase 20c)
- tools/meta/admin.py: get_logs() and run_diagnostic() added
- tools/registry.py: Both tools registered
- config/routes.yaml: Both tools added to tasks route
- tests/test_admin_tools.py: 8 tests
- Test floor: 445 passed, 0 failed
