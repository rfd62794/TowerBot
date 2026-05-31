# PrivyBot Roadmap

## Overview

PrivyBot is built in 15 phases — from core infrastructure to intelligent personal assistant. Each phase builds on the previous while maintaining the primitive builder philosophy: Python 3.12, SQLite, asyncio, free LLMs, your own hardware, your own hands.

**15 phases total. 8 complete. 53% done.**

**Current state (May 2026):**
- Morning briefing fires at 7AM — channel stats, calendar, Gmail, personal tasks, weather, weekly focus
- 46 tools across YouTube, Gmail, Calendar, Tasks, Steam, weather, web search, memory, personal tasks
- Layer 7 cluster operational: CacheManager, RateLimitManager, PollingManager
- Self-healing deployment with Telegram-triggered rollback
- 288/288 tests passing on dev branch
- 5 SDDs, 33 ADRs documenting all architecture decisions

**The gap that remains:** PrivyBot is Stable and Useful. The distance between current state and true Assistant is the intelligence layer — 27 manually seeded facts vs the corpus of hundreds of hours of Claude and Gemini conversation history that contains every architectural decision, project context, and personal detail Robert has shared. Phase 15 closes that gap.

---

## Phase 1 — Core Infrastructure ✅ DONE

**Status**: Complete
**Key Deliverables**:
- 6-layer architecture (transport → router → agent → report → memory → db)
- SQLite database with threads, messages, memory, model_status tables
- Tool registry system
- Telegram bot integration (python-telegram-bot)
- OpenRouter LLM client with free model fallback rotation

**Key Decisions**:
- Layered architecture for separation of concerns
- SQLite for simplicity, reliability, and privacy
- Tool registry for extensibility
- Free model rotation on 429 throttling
- Windows SelectorEventLoop for TLS compatibility

**Unlocked**: Foundation. Extensible tool system. Reliable async communication.

**Related ADRs**: ADR-001, ADR-002, ADR-003

---

## Phase 2 — Intelligence ✅ DONE

**Status**: Complete
**Key Deliverables**:
- Memory system with 27 seeded memories (context.yaml)
- Focus tracking — current project injected into system prompt
- Commitment system — save_commitment, list_commitments
- Nightly conversation summarization at 23:59
- Credential health checks at startup

**Key Decisions**:
- Memory seeded via context.yaml for personalization
- Focus injected into system prompt for grounding
- Nightly summary preserves conversation history across context resets
- Credential checks warn but do not block startup

**Unlocked**: Agent knows user context. Commitments tracked. Daily summaries. Self-validating health.

**Related ADRs**: ADR-004, ADR-005, ADR-006, ADR-007, ADR-008

---

## Phase 3 — Data Retention ✅ DONE

**Status**: Complete
**Key Deliverables**:
- 5 historical tables: channel_history, video_history, game_history, weather_history, video_metadata_cache, scheduled_videos
- Cache wrappers for all 21 tools (was 9/21, now 21/21)
- Context enrichment for channel and game metrics
- Morning briefing enriched with trend data

**Key Decisions**:
- Cache (short-term, TTL) separate from history (long-term, permanent)
- TTL policy per tool based on staleness tolerance
- Trend data returned when history exists — agent sees up/down not just point-in-time
- 90-day game history window; 7-day scheduled video cleanup

**Unlocked**: Reduced API quota usage. Historical trend analysis. Richer briefing.

**Related ADRs**: ADR-014

---

## Phase 4 — Proactive Scheduling ✅ DONE

**Status**: Complete
**Key Deliverables**:
- Hourly heartbeat check
- Task queue with three priority levels (critical, high, normal)
- Sleep hours suppression (midnight–7AM Eastern)
- Morning briefing flushes overnight queue
- Content gap detection (3–7 day warning)
- Game trend spike detection (>20% player change)

**Key Decisions**:
- Hourly heartbeat balances responsiveness vs resource use
- Sleep hours suppress non-critical alerts
- Briefing batches overnight alerts rather than sending each immediately

**Unlocked**: Proactive observations. Sleep hours respected. Content gaps detected. Game trends monitored.

**Related ADRs**: ADR-015

---

## Phase 5 — Calendar + Schedule ✅ DONE

**Status**: Complete
**Key Deliverables**:
- Google Calendar API (get_today_schedule, get_upcoming_events, check_availability)
- Google Tasks API — bidirectional sync with personal_tasks table
- Gmail API — dual account support (cheater2478@gmail.com + RFDITServices@gmail.com)
- Morning briefing enriched with calendar events and email unread counts
- Heartbeat checks: Google Tasks sync, personal task reminders

**Key Decisions**:
- OAuth token per account — personal and RFD IT Services authorized separately
- RFD credentials handled gracefully when token absent
- Tasks sync on startup and via /sync command
- Dual Gmail merged into single briefing section

**Unlocked**: Agent knows your schedule. Email monitored across two accounts. Task sync with Google.

**Related ADRs**: ADR-016, ADR-017

---

## Phase 6 — Goals + Plans ✅ DONE

**Status**: Complete
**Key Deliverables**:
- 4 tables: goals, milestones, tasks, weekly_plans
- config/goals.yaml + config/plans.yaml (source of truth for seed data)
- scripts/seed_goals.py — idempotent seeding
- 7 Telegram commands: /goals, /goal, /tasks, /plan, /task done, /confirm, /reject
- Heartbeat task reminders (60-minute window, overdue detection)
- Morning briefing: today's tasks + weekly focus

**Key Decisions**:
- Agent NEVER updates goals autonomously — suggests via suggest_goal_progress only
- YAML is source of truth for initial data; DB for runtime state
- Weekly plans aligned with nightly summary rhythm

**Unlocked**: Long-term goal tracking. Structured planning. Heartbeat reminders. Briefing tells you what to work on.

**Related ADRs**: ADR-017 (Goals and Plans System — to be written)

---

## Phase 7 — Tower Deployment 🖥️ PLANNED

**Status**: Planned
**Key Deliverables**:
- NSSM service installation on Tower (i5 4-core, 32GB RAM, no GPU)
- Ollama installation on Tower — nomic-embed-text + gemma3:4b (satisfies Phase 15 on Tower)
- Remote deploy via /deploy Telegram command
- start_stream tool — OBS WebSocket integration
- Persistent uptime — no laptop dependency

**Key Decisions**:
- Tower as dedicated PrivyBot host
- NSSM for Windows service management
- Ollama included in Phase 7 setup — required for mem0 (Phase 15) on Tower
- OBS WebSocket for stream control
- Phase 9 background task integration follows Phase 7

**Unlocked**: 24/7 operation on dedicated hardware. Stream control via Telegram. Phase 9 and Tower mem0 unblocked.

**Related ADRs**: ADR-019 (Tower Deployment — to be written)

---

## Phase 8 — Publish 📚 FUTURE

**Status**: Future
**Key Deliverables**:
- Gumroad guide: "Build Your Own Personal AI"
- Extract primitives as reusable packages
- Open-source PrivyBot (personal data removed)
- Community documentation

**Key Decisions**:
- Guide format: markdown + code examples
- Primitives: db layer, tool registry, scheduler
- License: MIT
- Pricing: pay-what-you-want

**Prerequisite**: Phase 7 stable and documented. Phase 15 complete and demonstrable.

**Related ADRs**: ADR-020 (Publishing Strategy — to be written)

---

## Phase 9 — Local Model for Background Tasks 🤖 PLANNED

**Status**: Planned (Ollama on Nitro already satisfied — Tower pending Phase 7)
**Key Deliverables**:
- call_background_model() in llm_client.py
- Nightly summary uses local model instead of OpenRouter
- Weekly goal synthesis uses local model
- Long-form content draft generation

**Key Decisions**:
- Local model for background tasks ONLY — never in conversation handler
- Real-time conversation stays on OpenRouter
- Model: gemma3:4b (already required for Phase 15 mem0 extraction)
- Estimated Tower speed: 3–5 tokens/sec on CPU-only i5 — acceptable for batch tasks
- Environment flag: LOCAL_MODEL_MODE=background
- Ollama on Nitro: already installed as of May 2026
- Ollama on Tower: installed during Phase 7 — Phase 9 follows immediately after

**Use Cases**: Nightly summary, weekly goal synthesis, long-form drafts, transcription analysis

**Unlocked**: Zero-cost background processing. Full privacy for sensitive summaries. No OpenRouter quota used for batch tasks.

**Related ADRs**: ADR-018 (Local Model Integration — to be written)

---

## Phase 10 — Offline-First Cache Strategy ✅ DONE

**Status**: Complete
**Key Deliverables**:
- CacheManager (infra/cache.py) — single owner of all cache behavior
- DBManager (infra/db/manager.py) — single owner of database access with retry
- BaseAPIHandler (api/_handler.py) — base class enforcing cache + rate limit patterns
- BaseTool (tools/_tool.py) — base class enforcing ok/stale_notice/error_code return shape
- RateLimitManager (infra/rate_limits.py) — proactive rate limit tracking
- 11/11 API files migrated to BaseAPIHandler pattern
- fetch_url tool — browser tool (requests + BeautifulSoup, cache per URL, TTL 1h)
- think tool — scratchpad for context continuity across model switches
- WAL mode enabled for concurrent access

**Key Decisions**:
- Staleness budget per API — some data ages slowly (YouTube, Steam)
- On API failure: return stale data with timestamp notice rather than error
- Stale notice format: "⚠️ Data from 4h ago (2026-05-30 09:15)"
- Write operations (Google Tasks push/complete/delete) bypass cache entirely
- Time-sensitive calls use stale_ok=False (calendar get_events_soon)

**Unlocked**: Bot functional during API outages. Consistent return shapes. Proactive rate limit awareness. Stale notice surfaced to user.

**Related ADRs**: ADR-018, ADR-019, ADR-020, ADR-022, ADR-023, ADR-024, ADR-025, ADR-026

---

## Phase 11 — API Hardening + Typed Returns 🔒 MOSTLY COMPLETE

**Status**: Mostly Complete (~85%)
**Duration**: Completed incrementally during Phase 10 and Layer 7 work

**Completed (during Phase 10 migration):**
- RateLimitManager ✅ — DB tables (api_rate_limits, api_call_log), singleton, BaseAPIHandler integration, quota visibility in /status (ADR-026: Accepted)
- fetch_url ✅ — FetchAPIHandler(BaseAPIHandler), cache per URL+max_chars, TTL 1h
- All API functions return dict ✅ — enforced by BaseAPIHandler pattern
- BaseTool return shape ✅ — ok/stale_notice/error_code on all tool returns
- Caller audit ✅ — all callers updated during Phase 10 migration
- Error contracts ✅ — standardized via BaseAPIHandler/BaseTool
- Test assertions ✅ — 288/288 passing with new return shapes

**Remaining:**
- Formal Python type hints (return type annotations, parameter types) on API and tool functions

**Related ADRs**: ADR-021 (API Return Type Standardization — to be written), ADR-026

---

## Phase 12 — DB Hardening 💾 IN PROGRESS

**Status**: In Progress (~40%)

**Completed:**
- DBManager ✅ — single owner of DB access, exponential backoff retry, WAL mode
- UNIQUE partial index on personal_tasks(title, due_date) WHERE status='pending' ✅ (ADR-030)
- INSERT OR IGNORE on add_personal_task() ✅
- 24h dedup window on save_commitment() ✅ (ADR-030)
- INSERT OR REPLACE on record_channel_day() + record_weather_day() ✅ (ADR-030)
- Missed task push-forward + recurrence recovery ✅ (ADR-031)
- Timestamp-fence test teardown — eliminates test DB pollution ✅

**Remaining:**
- Connection pooling (5-connection pool)
- Transaction management (explicit BEGIN/COMMIT/ROLLBACK)
- Migration versioning (schema_migrations table, rollback SQL)
- Vacuum/cleanup strategy (weekly Sunday 4AM)
- Backup mechanism (daily 3AM, retain 7 days)
- Connection health checks

**Related ADRs**: ADR-022 (DB Hardening Strategy — to be written), ADR-023, ADR-030, ADR-031

---

## Phase 13 — Logging Infrastructure 📊 PLANNED

**Status**: Planned
**Key Deliverables**:
- Structured logging: JSON with timestamp, level, trace_id, module, message
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Log rotation: daily, retain 30 days (logs/ directory)
- Request tracing: trace_id via async contextvars
- Performance metrics: API call duration in ms, tool execution time
- Error aggregation: deduplicate similar errors, alert on spikes

**Unlocked**: Production observability. Performance visibility. Error pattern detection.

**Related ADRs**: ADR-023 (Logging Infrastructure — to be written)

---

## Phase 14 — PollingManager ✅ DONE

**Status**: Complete
**Key Deliverables**:
- PollingManager (infra/polling.py) — Layer 7c, singleton, parallel to CacheManager + RateLimitManager
- Per-key intervals matching CacheManager TTLs exactly
- Checks RateLimitManager before firing — no polls during API cooldown
- Checks CacheManager — skips poll if data still fresh
- wait_for(key, timeout) — briefing waits for in-progress polls before reading
- poll_log DB table — tracks every poll attempt, duration, from_cache, error
- Absorbs: startup preload, heartbeat data fetching, _initial_sync

**Key Decisions (polling intervals):**
- gmail_personal, gmail_rfd, google_tasks: 300s (5min)
- calendar_today: 900s (15min)
- weather: 3600s (1h)
- youtube_channel, steam_library: 86400s (24h)
- ddg, wikipedia, reddit: None (on-demand only)

**Unlocked**: Each source polls at correct rate. Gmail fresh at 5min. Briefing always reads warm cache. Single polling control point.

**Related ADRs**: ADR-027

---

## Phase 15 — Intelligence Layer 🧠 PLANNED

**Status**: Planned — begins on Nitro immediately (Ollama already installed)
**Duration**: 2 weeks estimated

**Key Deliverables:**

**mem0 integration (ADR-032):**
- Local mem0 — Memory class (self-hosted), not MemoryClient (mem0.ai platform)
- MEM0_TELEMETRY=false
- Embedding: nomic-embed-text via Ollama (~274MB, CPU-friendly, strong on short queries)
- Extraction: gemma3:4b via Ollama (128K context, handles long conversation exports)
- Vector store: Chroma (local SQLite backend, pip install chromadb, no Docker)
- Zero external API calls for all memory operations
- MemoryManager (infra/memory_manager.py) — wraps mem0, parallel to existing SQLite memory table
- System prompt: semantic results (mem0.search) + structured results (list_memories()) combined
- scripts/migrate_memories_to_mem0.py — migrates existing 27 memories on first run
- scripts/pre_dump_memories.py — ingests Claude + Gemini conversation exports in batches

**MCP compatibility (ADR-033):**
- infra/mcp_server.py — standalone process, not embedded in bot
- pip install mcp (Anthropic MCP Python SDK)
- stdio transport for Claude Desktop — local only, no network exposure
- All 46 tools exposed — TOOL_REGISTRY is single source of truth
- One converter: OpenAI JSON Schema → MCP inputSchema
- Claude memory pipeline: Claude calls save_memory, update_memory via MCP during architecture sessions — organic, continuous ingestion without batch exports
- Claude Desktop config in README

**httpx:**
- pip install httpx
- Async HTTP client — better asyncio integration than requests for async contexts

**APScheduler (lower priority):**
- Custom scheduler works; APScheduler is a future cleanup if complexity warrants it

**Ollama models required:**
```
ollama pull nomic-embed-text   # 274MB, embedding
ollama pull gemma3:4b          # ~2.5GB, extraction + Phase 9 background tasks
```

**Dependency chain:**
```
mem0 + pre-dump                ← intelligence leap
    requires Ollama (Nitro ✅ now; Tower during Phase 7)
             Chroma (pip install chromadb)
             httpx  (pip install httpx)

MCP server                     ← closes Claude ↔ PrivyBot loop
    requires mcp (pip install mcp)
    independent of mem0

APScheduler                    ← scheduler cleanup, low priority
```

**Unlocked**: Semantic memory search. Deep context from conversation history. Claude calls PrivyBot tools directly. Organic memory growth via MCP during Claude sessions. True multi-system collaboration.

**Related ADRs**: ADR-032 (mem0 Integration), ADR-033 (MCP Compatibility)

---

## Phase Progress Summary

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1 — Core | ✅ DONE | 100% |
| Phase 2 — Intelligence | ✅ DONE | 100% |
| Phase 3 — Data | ✅ DONE | 100% |
| Phase 4 — Proactive | ✅ DONE | 100% |
| Phase 5 — Calendar | ✅ DONE | 100% |
| Phase 6 — Goals | ✅ DONE | 100% |
| Phase 7 — Tower | 🖥️ PLANNED | 0% |
| Phase 8 — Publish | 📚 FUTURE | 0% |
| Phase 9 — Local Model | 🤖 PLANNED | 0% |
| Phase 10 — Offline Cache | ✅ DONE | 100% |
| Phase 11 — API Hardening | 🔒 MOSTLY COMPLETE | 85% |
| Phase 12 — DB Hardening | 💾 IN PROGRESS | 40% |
| Phase 13 — Logging | 📊 PLANNED | 0% |
| Phase 14 — PollingManager | ✅ DONE | 100% |
| Phase 15 — Intelligence Layer | 🧠 PLANNED | 0% |

**Overall Progress**: 53% (8/15 phases complete)

---

## Build Sequence — Recommended Order

Phase numbers reflect design order, not optimal build order. This section gives the recommended execution sequence:

**Now (Nitro, no external dependencies):**
1. Phase 15 — mem0 + MCP — Ollama already on Nitro, start immediately

**After Phase 15 stable:**
2. Phase 7 — Tower deployment (includes Ollama on Tower; unlocks Phase 9)
3. Phase 9 — Background task models (nightly summary, weekly synthesis via local Ollama)

**Ongoing (no external dependencies, parallelizable):**
4. Phase 12 — Complete DB hardening (connection pooling, migration versioning, backup)
5. Phase 11 — Add formal type hints (remaining ~15% of Phase 11)
6. Phase 13 — Logging infrastructure

**Future:**
7. Phase 8 — Publish (after Phase 7 + 15 stable, demonstrable, documented)

---

## Next Steps

**Phase 15 — start now on Nitro:**
1. `pip install mem0ai chromadb httpx mcp` 
2. `ollama pull nomic-embed-text && ollama pull gemma3:4b` 
3. Build `infra/memory_manager.py` — MemoryManager wrapping mem0
4. Build `scripts/migrate_memories_to_mem0.py` — migrate existing 27 memories
5. Build `scripts/pre_dump_memories.py` — ingest Claude + Gemini exports
6. Update `bot/agent.py` — _system_prompt() combines semantic + structured memory
7. Update get_memories tool — routes through MemoryManager
8. Build `infra/mcp_server.py` — MCP server wrapping TOOL_REGISTRY
9. Configure Claude Desktop with MCP server config
10. Export Claude conversation history → run pre-dump → verify semantic search

**Phase 7 — Tower (when ready):**
1. NSSM service installation
2. `ollama pull nomic-embed-text && ollama pull gemma3:4b` on Tower
3. Remote deploy via /deploy command
4. OBS WebSocket integration
5. Verify PrivyBot + mem0 on Tower hardware

---

## Philosophy Reminder

This roadmap is not a sprint. It is a record of a personal AI system being built deliberately, layer by layer, with full understanding of every component.

PrivyBot:
- Costs nothing to run
- Lives on your hardware
- Knows you deeply
- Acts proactively on your behalf
- Gets smarter as you use it — every Claude session can pump memories directly via MCP

The primitive builder's promise: no frameworks you don't understand, no cloud dependencies you don't control, no data that leaves without your knowledge.
