# Comprehensive Outstanding Work - All Documented Plans

## IMMEDIATE (This Session - Phase 30 Completion)

### Critical Path for Tower Deployment
- [ ] **Push Phase 30 to main** - Currently on dev branch, never merged or pushed
- [ ] **Update Tower** - `git pull` + NSSM restart to deploy Phase 30
- [ ] **Telegram live verification** - Run `run_named_command("privy_tests")` and `list_services` to confirm live status
- [ ] **purge_null_tasks** - 753 null tasks in database, never cleared

### Phase 30 Deferred Items
- [ ] **3 memory_semantic Chroma failures** - Deferred for weekend assessment (not blocking Tower)
- [ ] **YouTube + itch.io MCP tools for daily brief** - Declared, not built

---

## PHASE 31 (Declared in Handoff)

### Test Floor Expansion
- [ ] **6 task_notifications anchor tests** from Phase 29 §3 - Floor moves from 345 to 351

### New Tool Integrations
- [ ] **GitHub Issues tools** - 4 tools via GraphQL (`create_issue`, `list_issues`, `update_issue`, `add_to_project`)
- [ ] **ContentPipeline as MCP Tower service** - Wrap ContentEngine as FastMCP endpoints, NSSM service
- [ ] **OneDrive folder watching** - `check_video_folder`, queue new videos to ContentPipeline
- [ ] **Custom Playwright MCP server** - `PlaywrightBase`, `TeleseroTools`, `ItchioTools` extensions, per-site `storageState` JSON, NSSM service: `PrivybotPlaywright`
- [ ] **rfditservices.com WordPress tools** - Separate Application Password needed from site admin
- [ ] **Dev.to publishing tools** - httpx, REST API, no Playwright

---

## ROADMAP PHASES (Not Complete)

### Phase 7 — Tower Deployment (0%)
- [ ] NSSM service installation on Tower
- [ ] Ollama installation on Tower (nomic-embed-text + gemma3:4b)
- [ ] Remote deploy via /deploy Telegram command
- [ ] start_stream tool — OBS WebSocket integration
- [ ] Persistent uptime — no laptop dependency

### Phase 8 — Publish (0%)
- [ ] Gumroad guide: "Build Your Own Personal AI"
- [ ] Extract primitives as reusable packages
- [ ] Open-source PrivyBot (personal data removed)
- [ ] Community documentation

### Phase 9 — Local Model for Background Tasks (0%)
- [ ] call_background_model() in llm_client.py
- [ ] Nightly summary uses local model instead of OpenRouter
- [ ] Weekly goal synthesis uses local model
- [ ] Long-form content draft generation

### Phase 11 — API Hardening (85% complete)
- [ ] Formal Python type hints (return type annotations, parameter types) on API and tool functions

### Phase 12 — DB Hardening (40% complete)
- [ ] Connection pooling (5-connection pool)
- [ ] Transaction management (explicit BEGIN/COMMIT/ROLLBACK)
- [ ] Migration versioning (schema_migrations table, rollback SQL)
- [ ] Vacuum/cleanup strategy (weekly Sunday 4AM)
- [ ] Backup mechanism (daily 3AM, retain 7 days)
- [ ] Connection health checks

### Phase 13 — Logging Infrastructure (0%)
- [ ] Structured logging: JSON with timestamp, level, trace_id, module, message
- [ ] Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- [ ] Log rotation: daily, retain 30 days (logs/ directory)
- [ ] Request tracing: trace_id via async contextvars
- [ ] Performance metrics: API call duration in ms, tool execution time
- [ ] Error aggregation: deduplicate similar errors, alert on spikes

### Phase 15 — Intelligence Layer (0%)
- [ ] mem0 integration (Memory class, not MemoryClient)
- [ ] MEM0_TELEMETRY=false
- [ ] Embedding: nomic-embed-text via Ollama
- [ ] Extraction: gemma3:4b via Ollama
- [ ] Vector store: Chroma (local SQLite backend)
- [ ] MemoryManager (infra/memory_manager.py)
- [ ] System prompt: semantic results + structured results combined
- [ ] scripts/migrate_memories_to_mem0.py
- [ ] scripts/pre_dump_memories.py
- [ ] MCP server (infra/mcp_server.py) - stdio transport for Claude Desktop
- [ ] All 46 tools exposed via MCP
- [ ] Claude Desktop config in README
- [ ] httpx async HTTP client
- [ ] APScheduler (lower priority)

---

## MCP SERVER (Phase 30 Partial, Phase 15 Partial)

### Completed (Phase 30)
- [x] MCP dual-transport server (infra/mcp/server.py)
- [x] stdio transport for Claude Desktop
- [x] MCP_EXPOSED_TOOLS curated set
- [x] JWT auth for SSE transport
- [x] MCP fast variants (get_memories, read_current_state, find_opportunities)

### Not Implemented
- [ ] SSE transport with JWT auth (Tower deployment)
- [ ] Tailscale Funnel for remote access (https://nitro.ts.net/mcp)
- [ ] /mcp_token Telegram command
- [ ] Claude Desktop config in README

---

## AUTONOMOUS TASKS (Partially Complete)

### Completed (Phase 30)
- [x] APScheduler integration
- [x] 4 autonomous tasks running (email_triage, nightly_snapshot, itch_reddit_check, openagent_momentum_tracker)
- [x] agent_actions table
- [x] Overnight actions in morning briefing

### Not Implemented (autonomous-expansion.md)
- [ ] blog_structure_generator (Sunday 1AM) - Generate blog post skeleton using RFD Content Frame
- [ ] community_opportunity_scout (Every 3h, 7AM–11PM) - Monitor r/incremental_games, r/bevy, r/rust, r/gamedev
- [ ] consulting_lead_scout (Daily 7AM) - Search for Python, Rust, data automation, Selenium contract work

### Not Implemented (autonomous-synthesis-creation.md)
- [ ] content_code_gap_analyzer (3AM daily) - Cross-reference commits with YouTube content library
- [ ] itch_cause_finder (weekly) - Correlate itch.io download spikes with Reddit posts, YouTube uploads, commit activity
- [ ] commit_velocity_sentinel (daily) - Track commits per day, identify stalled projects
- [ ] voidrift_devlog_outline (every 2 weeks) - Generate structured devlog outline
- [ ] rfditservices_post_draft (Sunday 2AM) - Write blog post skeleton in RFD Content Frame
- [ ] openagent_patch_notes (when new commits detected) - Draft release notes + LinkedIn post
- [ ] task_output_reviewer (Sunday 4AM) - Audit autonomous task usefulness
- [ ] quota_pattern_analyzer (weekly) - Analyze quota usage vs value produced
- [ ] Event-driven architecture - Trigger conditions for tasks

### Not Implemented (idle-fallback-tasks.md)
- [ ] Fallback task pool (5 micro-tasks)
- [ ] Detection logic in run_autonomous_task()
- [ ] _count_consecutive_empty_runs()
- [ ] Fallback stats in morning briefing

---

## SEMANTIC MEMORY (Partially Complete)

### Completed
- [x] Chroma installation verified (working locally)

### Not Implemented (semantic-memory-chroma-23c3c0.md)
- [ ] infra/memory_manager.py - MemoryManager singleton
- [ ] Chroma collection with OllamaEmbeddingFunction (nomic-embed-text)
- [ ] SQLite + Chroma dual-write architecture
- [ ] scripts/migrate_memories_to_chroma.py
- [ ] tests/test_memory_semantic.py (4 tests)
- [ ] bot/memory.py routing through memory_manager

### Current Status
- 3 memory_semantic test failures (Chroma integration not complete)

---

## WORDPRESS BLOG TOOLS (Not Implemented)

### Not Implemented (wordpress-blog-tools.md)
- [ ] api/web/wordpress_api.py - WordPressAPIHandler(BaseAPIHandler)
- [ ] tools/communication/blog.py - BlogTools(BaseTool)
- [ ] TOOL_REGISTRY entries (4 tools: get_blog_posts, get_blog_post, create_blog_draft, update_blog_post)
- [ ] Environment variables (WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
- [ ] infra/cache.py TTL entries
- [ ] bot/autonomous.py blog_structure_generator prompt update
- [ ] tests/test_wordpress_api.py

---

## BUDGET TRACKING (Not Implemented)

### Not Implemented (budget-tracking-mcp-expansion.md)
- [ ] openrouter_usage table (task_context, model, is_free, prompt_tokens, completion_tokens, estimated_cost_usd, called_at)
- [ ] model_manager.py changes (MAX_DAILY_PAID_USD = 0.10, can_use_paid_model())
- [ ] Every model call logged to DB
- [ ] Paid calls trigger immediate Telegram alert
- [ ] /status shows today's cost, this week's cost, free vs paid ratio

---

## SELF-DEPLOY SYSTEM (Not Implemented)

### Not Implemented (self-deploy-system-23c3c0.md)
- [ ] /deploy command with inline git pull + verify + self-restart (bot/router.py)
- [ ] launch.py crash-revert watchdog (new file, repo root)
- [ ] tests/test_deploy.py (6 tests)
- [ ] .deploy_restart flag file

---

## SELF-EXPANSION LOOP (Not Implemented)

### Not Implemented (self-expansion-loop.md)
- [ ] Plan docs → ADRs and SDDs conversion process
- [ ] ADR-034: OpenRouter Budget Tracking
- [ ] ADR-033 revision: MCP HTTP+SSE+JWT
- [ ] SDD_Budget_Tracking.md
- [ ] SDD_MCP_HTTP_Server.md
- [ ] ADR-035: Autonomous Task Architecture
- [ ] SDD_Autonomous_Tasks.md
- [ ] read_local_file tool (or GitHub API tools)
- [ ] self_expansion_planner autonomous task
- [ ] OpenAgent integration (BLOCKED - OpenAgent package has bugs)

---

## GOOGLE PHASE 2 MIGRATION (Not Implemented)

### Not Implemented (google-phase2-9a9e8a.md)
- [ ] Gmail API migration to BaseAPIHandler (tools/api/gmail_api.py)
- [ ] Gmail tool layer unwrapping (tools/gmail.py)
- [ ] Gmail tests update (tests/test_gmail.py)
- [ ] Gmail TTL entries (core/cache.py)
- [ ] Calendar API migration to BaseAPIHandler (tools/api/google_calendar_api.py)
- [ ] Calendar tool layer unwrapping (tools/calendar.py)
- [ ] Calendar tests update (tests/test_google_calendar.py)
- [ ] Calendar TTL entries (core/cache.py)
- [ ] Tasks API migration to BaseAPIHandler (tools/api/google_tasks_api.py)
- [ ] Tasks sync update (tools/sync_tasks.py)
- [ ] Tasks tests update (tests/test_google_tasks_sync.py)
- [ ] Tasks TTL entries (core/cache.py)
- [ ] Scheduler heartbeat update (core/scheduler.py)

---

## THINKING THREAD (Not Implemented)

### Not Implemented (thinking-thread-23c3c0.md)
- [ ] _thinking_thread() in bot/transport.py
- [ ] THINKING_MESSAGES list
- [ ] Grace period (2s) before showing status
- [ ] Rotating status messages every 3s
- [ ] Delete message on completion
- [ ] tests/test_transport.py (+3 tests)

---

## ERROR SHAPES (Partially Complete)

### Not Implemented (item-3-error-shapes-a88f98.md)
- [ ] GoalsTools(BaseTool) class in tools/goals.py
- [ ] Move 4 functions into GoalsTools class
- [ ] RecommendationsTools(BaseTool) class in tools/recommendations.py
- [ ] Move get_content_recommendations into RecommendationsTools class
- [ ] Mark dead code in tools/games.py (line 137)
- [ ] Update tests if assertions break

---

## DIRECTORY RESTRUCTURE (Not Implemented)

### Not Implemented (phase-a-restructure-a88f98.md)
- [ ] Move core/ to bot/ (Layers 2-4) and infra/ (Layer 5)
- [ ] Update all import paths (bot/*, infra/*, tools/*, scripts/*, tests/*)
- [ ] Delete core/ directory after verification
- [ ] Branch: restructure

### Not Implemented (phase-b-tools-restructure-a88f98.md)
- [ ] Create category directories (tools/content, tools/games, tools/search, tools/productivity, tools/communication, tools/meta)
- [ ] Move files to new locations
- [ ] Create package __init__.py files
- [ ] Update imports in moved files
- [ ] Update tools/registry.py import paths
- [ ] Update bot/scheduler.py import paths
- [ ] Update test imports
- [ ] Delete old files after verification

---

## OPENROUTER HANDLER + OLLAMA FIX (Not Implemented)

### Not Implemented (openrouter-handler-ollama-fix-23c3c0.md)
- [ ] api/web/openrouter_api.py - OpenRouterAPIHandler class
- [ ] get_free_models() with 1h in-memory cache
- [ ] validate_model() method
- [ ] chat_completion() method
- [ ] model_manager.py: Remove deepseek/deepseek-v4-flash:free from SEED_FREE_MODELS
- [ ] model_manager.py: Wire fetch_free_tool_models() to OpenRouterAPIHandler
- [ ] model_manager.py: Add Ollama health check logging
- [ ] agent.py: Permanent 404 removal (_dead_models set)
- [ ] tests/test_openrouter_api.py (4 tests)

---

## DECLARED IN EARLIER SESSIONS, NEVER IMPLEMENTED

### Infrastructure
- [ ] **n8n as next infrastructure layer** - Self-hosted on Tower, bidirectional MCP, 400+ integrations (declared in CB Augmentation session)

---

## PHASE 32+ (Future Phases)

### Intent & Classification
- [ ] **Intent Classifier** with Pydantic structured outputs
- [ ] **Autonomous research loop** - DuckDuckGo + Reddit + web fetch when idle
- [ ] **Did You Know notification system**

### Memory & History
- [ ] **Conversation history** - SQLite FTS5 + Chroma semantic search
- [ ] **Shot bank** for few-shot examples

---

## PHASE 33+ (Future Phases)

### Prompt Engineering
- [ ] **Prompt library** - `system/ + skills/ + formats/ + registry.yaml`
- [ ] **Self-improving prompts** - OPRO/SIPDO pattern

---

## OTHER OUTSTANDING

### Content
- [ ] **Blog post 16 ("Nine Projects, One Loop")** - Content integrity unverified

### External Deployments
- [ ] **RFD_Sheets_MCP Tower deployment** - Pending multiple sessions

---

## TEST FLOOR STATUS

**Current:** 345 passed, 3 failed, 0 skipped
- 3 memory_semantic Chroma failures (deferred)

**Target:** 351 passed, 0 failed, 0 skipped
- Requires 6 task_notifications anchor tests from Phase 29 §3

---

## COMPLETED IN EARLIER SESSIONS (For Reference)

- [x] fetch_url + think tools (fetch-url-think-tools-9a9e8a.md)
- [x] Fix circular import in memory tools (fix-circular-import-9a9e8a.md)
- [x] Fix fetch rate limit (fix-fetch-rate-limit-a88f98.md)
- [x] RateLimitManager implementation (ratelimitmanager-9a9e8a.md)
- [x] Autonomous operation (autonomous-operation-23c3c0.md)
