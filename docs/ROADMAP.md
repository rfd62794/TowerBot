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

## Phase 5 — Calendar + Schedule 📅 PLANNED

**Status**: Planned
**Duration**: 2 weeks
**Key Deliverables**:
- YouTube Data API v3 integration
- get_scheduled_videos() tool
- get_video_metadata() tool
- Google Calendar API integration
- get_upcoming_events() tool
- get_today_schedule() tool
- OAuth scope addition for calendar access

**Key Decisions**:
- Re-auth required for calendar scope
- Video metadata cached (stable reference data)
- Scheduled videos auto-cleanup after 7 days
- Calendar events integrated into morning briefing

**Unlocked**:
- Agent knows your schedule
- Video publishing tracked
- Calendar gaps detected
- Briefing includes today's events

**Related ADRs**:
- ADR-017: Calendar Integration (to be written)

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

## Phase Progress Summary

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1 — Core | ✅ DONE | 100% |
| Phase 2 — Intelligence | ✅ DONE | 100% |
| Phase 3 — Data | ✅ DONE | 100% |
| Phase 4 — Proactive | ✅ DONE | 100% |
| Phase 5 — Calendar | 📅 PLANNED | 0% |
| Phase 6 — Goals | 🎯 DONE | 100% |
| Phase 7 — Tower | 🖥️ PLANNED | 0% |
| Phase 8 — Publish | 📚 FUTURE | 0% |
| Phase 9 — Local Model | 🤖 PLANNED | 0% |

**Overall Progress**: 56% (5/9 phases complete)

---

## Next Steps

1. **Build Phase 5** (Calendar + Schedule):
   - YouTube Data API v3 integration
   - Google Calendar OAuth
   - Video metadata and scheduled videos tools

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
