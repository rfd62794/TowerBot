# PrivyBot Roadmap

## Overview
PrivyBot evolves in 8 phases, from core infrastructure to proactive intelligence to life management. Each phase builds on the previous, unlocking new capabilities while maintaining the primitive builder philosophy.

---

## Phase 1 — Core Infrastructure ✅ DONE

**Status**: Complete
**Duration**: Initial build
**Key Deliverables**:
- 6-layer architecture (transport → router → agent → report → memory → db)
- SQLite database with threads, messages, memory, model_status tables
- Tool registry system
- Telegram bot integration
- OpenRouter LLM client with fallback rotation

**Key Decisions**:
- Layered architecture for separation of concerns
- SQLite for simplicity and reliability
- Tool registry for extensibility
- Free model rotation on 429 throttling
- Windows SelectorEventLoop for TLS fix

**Unlocked**:
- Foundation for all subsequent phases
- Extensible tool system
- Reliable async communication

**Related ADRs**:
- ADR-001: Layered Architecture
- ADR-002: SQLite Choice
- ADR-003: Tool Registry

---

## Phase 2 — Intelligence ✅ DONE

**Status**: Complete
**Duration**: 2 weeks
**Key Deliverables**:
- Memory system with 26 seeded memories
- Focus tracking (current project context)
- Commitment system (save_commitment, get_commitments)
- Nightly conversation summarization
- Credential health checks at startup

**Key Decisions**:
- Memory seeded via context.yaml for personalization
- Focus injected into system prompt for grounding
- Commitments stored in memory table
- Nightly summary at 11:59PM via scheduler
- Credential checks warn but don't block startup

**Unlocked**:
- Agent knows user context without prompting
- Commitments tracked across conversations
- Daily summaries preserve conversation history
- System validates its own health

**Related ADRs**:
- ADR-004: Memory System
- ADR-005: Focus Injection
- ADR-006: Commitment Tracking
- ADR-007: Nightly Summarization
- ADR-008: Credential Health Checks

---

## Phase 3 — Data Retention ✅ DONE

**Status**: Complete
**Duration**: 1 week
**Key Deliverables**:
- 5 new historical tables: video_history, game_history, weather_history, video_metadata_cache, scheduled_videos
- Cache wrappers for all 21 tools (was 9/21, now 21/21)
- Context enrichment for channel and game metrics
- Morning briefing enriched with trends

**Key Decisions**:
- Separate cache (short-term) from history (long-term)
- TTL policy per tool based on data staleness
- Trend data returned when history exists
- 90-day game history window
- 7-day scheduled video cleanup

**Unlocked**:
- Reduced API quota usage (all tools cached)
- Historical trend analysis
- Agent sees "up vs down" not just point-in-time
- Morning briefing more informative

**Related ADRs**:
- ADR-014: Data Retention and Cache Strategy

---

## Phase 4 — Proactive Scheduling ✅ DONE

**Status**: Complete
**Duration**: 1 week
**Key Deliverables**:
- Hourly heartbeat check
- Task queue table with priority routing
- Time-aware routing (sleep hours suppression)
- Morning briefing flushes overnight queue
- Content gap detection (3-7 days)
- Game trend spike detection (>20%)

**Key Decisions**:
- Hourly heartbeat not per-minute (balance responsiveness vs resource)
- Sleep hours (midnight-7AM) suppress non-critical alerts
- Three priority levels: critical, high, normal
- Task queue for time-aware deferral
- Morning briefing batches overnight alerts

**Unlocked**:
- PrivyBot surfaces observations proactively
- Sleep hours respected
- Content gaps detected in advance
- Game trends monitored automatically

**Related ADRs**:
- ADR-015: Heartbeat and Proactive Scheduling

---

## Phase 5 — Calendar + Schedule ✅ DONE

**Status**: Complete
**Duration**: 2 weeks
**Key Deliverables**:
- Google Calendar API integration (tools/api/google_calendar_api.py)
- Google Tasks API integration (tools/api/google_tasks_api.py)
- Gmail API integration (tools/api/gmail_api.py)
- Dual Gmail account support (personal + RFD IT Services)
- Calendar tools: get_today_schedule, get_upcoming_events, check_availability
- Gmail tools: get_inbox_summary, search_email, check_sender
- Google Tasks sync: bidirectional sync with personal_tasks table
- Morning briefing enriched with calendar events and email summaries
- Heartbeat check 8: Google Tasks sync
- Heartbeat check 9: overdue/pending personal task reminders

**Key Decisions**:
- OAuth token per account (config/youtube_token.json, config/rfd_token.json)
- RFD credentials handled gracefully when token missing
- Tasks sync on startup and via /sync command
- Calendar events integrated into morning briefing
- Dual Gmail merged inbox summaries

**Unlocked**:
- Agent knows your schedule
- Email monitoring across two accounts
- Task sync between local DB and Google Tasks
- Briefing includes today's events and email status

**Related ADRs**:
- ADR-016: Dual Gmail Account Pattern
- ADR-017: Google OAuth Scope Management

---

## Phase 6 — Goals + Plans 🎯 DONE

**Status**: Complete
**Duration**: 1 day
**Key Deliverables**:
- 4 tables: goals, milestones, tasks, weekly_plans
- CRUD functions for all 4 tables
- config/goals.yaml with 4 active goals
- config/plans.yaml with current week plan
- scripts/seed_goals.py for idempotent seeding
- tools/goals.py with 7 functions
- 7 Telegram commands (/goals, /goal, /tasks, /plan, /task done, /confirm, /reject)
- Heartbeat task reminders (scheduled in 60 min, overdue detection)
- Morning briefing enriched with today's tasks and weekly focus
- 8 goals tools added to TOOL_REGISTRY

**Key Decisions**:
- Both Telegram commands + YAML (YAML is source of truth for initial data)
- Weekly plans with task breakdown (aligned with nightly summary rhythm)
- Agent suggests updates, you confirm or reject (balance of autonomy + control)
- Agent NEVER updates goals autonomously — only suggests via suggest_goal_progress

**Unlocked**:
- Long-term goal tracking (yearly → quarterly → monthly → weekly → daily)
- Structured planning system
- Agent helps plan your week
- Progress monitored automatically
- Morning briefing tells you what to work on
- Heartbeat reminds you when tasks are due

**Related ADRs**:
- ADR-017: Goals and Plans System (to be written)

---

## Phase 7 — Tower Deployment 🖥️ PLANNED

**Status**: Planned
**Duration**: 1 week
**Key Deliverables**:
- NSSM service installation on Tower
- Remote deploy via Telegram (/deploy command)
- start_stream tool (OBS integration)
- Morning briefing runs on Tower hardware
- Persistent uptime (no laptop required)

**Key Decisions**:
- Tower as dedicated PrivyBot host
- NSSM for Windows service management
- OBS WebSocket for stream control
- Remote deploy for updates

**Unlocked**:
- PrivyBot runs 24/7 on dedicated hardware
- Stream control via Telegram
- No laptop dependency
- True "always-on" assistant

**Related ADRs**:
- ADR-019: Tower Deployment (to be written)

---

## Phase 8 — Publish 📚 FUTURE

**Status**: Future
**Duration**: TBD
**Key Deliverables**:
- Gumroad guide: "Build Your Own Personal AI"
- Extract primitives as reusable packages
- Open-source PrivyBot (with personal data removed)
- Community documentation

**Key Decisions**:
- Guide format: markdown + code examples
- Primitives: db layer, tool registry, scheduler
- License: MIT
- Pricing: pay-what-you-want

**Unlocked**:
- Others can build their own personal AI
- PrivyBot primitives reused
- Knowledge shared with primitive builders
- Potential revenue from guide

**Related ADRs**:
- ADR-020: Publishing Strategy (to be written)

---

## Phase 9 — Local Model for Background Tasks 🤖 PLANNED

**Status**: Planned
**Duration**: 1 week (after Tower deploy)
**Hardware Confirmed**:
- CPU: i5 4-core (older generation)
- RAM: 32GB (sufficient, not the constraint)
- GPU: none

**Key Deliverables**:
- Ollama installation on Tower
- Gemma 4 E4B Q4 model pull (gemma4:4b)
- call_background_model() function in llm_client.py
- Nightly summary uses local model
- Weekly goal synthesis uses local model
- Long-form draft generation uses local model
- test_models.py validation for tool calling

**Key Decisions**:
- Local model used for background tasks ONLY
- Never called from conversation handler
- Real-time conversation stays on OpenRouter
- Model: gemma4:4b (Q4 quantized, ~5GB RAM)
- Estimated: 2-5 tokens/second on CPU-only i5
- Environment flag: LOCAL_MODEL_MODE=background

**Use Cases**:
- Nightly summary (midnight) — no urgency
- Weekly goal synthesis (Sunday night)
- Long-form content drafts (async)
- Transcription analysis (batch)

**Unlocked**:
- Zero cost for background processing
- Full privacy for sensitive summaries
- No impact on conversation responsiveness
- OpenRouter remains primary for conversation

**Future**: if GPU added to Tower
- Reassess for real-time conversation
- Gemma 4 E4B with GPU: 30-60 tok/s
- Switch LOCAL_MODEL_MODE=realtime

**Related ADRs**:
- ADR-018: Local Model Integration (to be written)

---

## Phase 10 — Offline-First Cache Strategy 🔄 IN PROGRESS

**Status**: In Progress (Phase 1 complete, Phase 2 pending)
**Duration**: 2 weeks
**Key Deliverables**:
- Phase 1 (Complete): Cache plumbing infrastructure
  - get_stale_cached_result() — returns cached data regardless of TTL
  - record_preload_result() — writes to tool_cache + preload_log
  - get_preload_status() — metadata on last fetch per tool
  - preload_log table — tracks fetch attempts, success, duration
  - tools/api/_base.py — cached_api_call() wrapper pattern
  - stale_notice() — human-readable staleness formatting
  - 15 tests, 124/124 passing
- Phase 2 (Pending): Wire all API files to use cached_api_call()
  - weather_api.py — 1 hour TTL
  - youtube_api.py — 6 hours (Analytics), 24 hours (Data)
  - steam_api.py — 24 hours
  - gmail_api.py — 5 minutes
  - google_calendar_api.py — 15 minutes
  - google_tasks_api.py — 5 minutes
  - itad_api.py, steamspy_api.py, ddg_api.py, wikipedia_api.py, reddit_api.py
- Phase 3 (Pending): Preloader on startup
  - scripts/preload.py — warm cache on bot startup
  - privybot.py _initial_sync — call run_preload()
  - scheduler.py health_check — stale data detection
  - scheduler.py morning_briefing — stale notice cap (max 2)

**Key Decisions**:
- Staleness budget per API — some data ages slowly (YouTube, Steam)
- On API failure: fall back to stale data with timestamp warning
- Preload on startup: reduce first-query latency
- Stale notice format: "⚠️ Data from 4h ago (2026-05-30 09:15)"
- Morning briefing stale notice cap: max 2 individual, then collapse to summary

**Unlocked**:
- Bot remains functional during API outages
- First query latency reduced via preload
- User informed when data is stale
- Reduced API quota usage

**Related ADRs**:
- ADR-018: Offline-First Cache Strategy
- ADR-019: Staleness Budget per API
- ADR-020: Preload on Startup Pattern

---

## Phase 11 — API Hardening + Typed Returns 🔒 PLANNED

**Status**: Planned
**Duration**: 1 week
**Key Deliverables**:
- Return type changes: all API functions return dict (not int/list)
- Tool unwrapping: tools/*.py unwrap dict data, add stale_notice
- Caller audit: verify all tool callers handle dict returns
- Test updates: update assertions for new return shapes
- Type hints: add proper type hints to all API functions
- Error contracts: standardize error dict format across all APIs

**Key Decisions**:
- API functions always return dict (even for simple int/list)
- Tool functions add stale_notice field when _stale=True
- Agent sees stale_notice field and surfaces to user
- No breaking changes to agent tool calling

**Unlocked**:
- Consistent return shapes across all APIs
- Staleness visible to agent and user
- Type safety improved
- Error handling standardized

**Related ADRs**:
- ADR-021: API Return Type Standardization (to be written)

---

## Phase 12 — DB Hardening 💾 PLANNED

**Status**: Planned
**Duration**: 1 week
**Key Deliverables**:
- Connection pooling: SQLite connection pool for concurrent access
- Transaction management: explicit BEGIN/COMMIT/ROLLBACK
- Migration versioning: track schema versions, apply migrations incrementally
- Vacuum/cleanup strategy: periodic VACUUM, index rebuild
- Backup mechanism: automated backups to S3 or local
- Connection health checks: detect and recover from stale connections

**Key Decisions**:
- Pool size: 5 connections (balance resource vs concurrency)
- Migration table: schema_migrations (version, applied_at, rollback_sql)
- Backup schedule: daily at 3AM, retain 7 days
- Vacuum schedule: weekly on Sunday at 4AM

**Unlocked**:
- Better concurrent access
- Safer schema changes
- Data loss protection
- Performance maintenance

**Related ADRs**:
- ADR-022: DB Hardening Strategy (to be written)

---

## Phase 13 — Logging Infrastructure 📊 PLANNED

**Status**: Planned
**Duration**: 1 week
**Key Deliverables**:
- Structured logging: JSON-formatted logs with consistent fields
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Log rotation: daily rotation, retain 30 days
- Request tracing: trace_id across async calls
- Performance metrics: log duration for API calls, tool execution
- Error aggregation: deduplicate similar errors, alert on spikes

**Key Decisions**:
- Log format: JSON with timestamp, level, trace_id, module, message
- Storage: logs/ directory, rotated by date
- Tracing: async contextvars for trace_id propagation
- Metrics: log API call duration in ms, tool execution time

**Unlocked**:
- Better debugging
- Performance visibility
- Error pattern detection
- Production observability

**Related ADRs**:
- ADR-023: Logging Infrastructure (to be written)

---

## Phase Progress Summary

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1 — Core | ✅ DONE | 100% |
| Phase 2 — Intelligence | ✅ DONE | 100% |
| Phase 3 — Data | ✅ DONE | 100% |
| Phase 4 — Proactive | ✅ DONE | 100% |
| Phase 5 — Calendar | ✅ DONE | 100% |
| Phase 6 — Goals | 🎯 DONE | 100% |
| Phase 7 — Tower | 🖥️ PLANNED | 0% |
| Phase 8 — Publish | 📚 FUTURE | 0% |
| Phase 9 — Local Model | 🤖 PLANNED | 0% |
| Phase 10 — Offline Cache | 🔄 IN PROGRESS | 10% |
| Phase 11 — API Hardening | 🔒 PLANNED | 0% |
| Phase 12 — DB Hardening | 💾 PLANNED | 0% |
| Phase 13 — Logging | 📊 PLANNED | 0% |

**Overall Progress**: 46% (6/13 phases complete)

---

## Next Steps

1. **Complete Phase 10** (Offline-First Cache):
   - Phase 2: Wire all API files to use cached_api_call()
   - Phase 3: Preloader on startup

2. **Build Phase 7** (Tower Deployment):
   - NSSM service installation
   - Remote deploy via /deploy command
   - OBS WebSocket integration

3. **Build Phase 9** (Local Model for Background Tasks):
   - After Tower deploy, install Ollama
   - Pull gemma4:4b model
   - Add call_background_model() to llm_client.py
   - Test inference speed on Tower hardware
   - If < 90 seconds: enable for nightly summary

---

## Philosophy Reminder

This roadmap is not a sprint. It's a journey of building a personal AI system that:
- Costs nothing to run
- Lives on your hardware
- Knows you deeply
- Acts proactively on your behalf

Each phase unlocks new capabilities while maintaining the primitive builder identity: simple, clean, extensible, free.
