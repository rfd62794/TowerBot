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
- ADR-016: Calendar Integration (to be written)

---

## Phase 6 — Goals + Plans 🎯 PLANNED

**Status**: Planned
**Duration**: 2 weeks
**Key Deliverables**:
- Goals table (id, title, target_date, status, progress)
- Milestones table (linked to goals)
- Weekly plans table (linked to goals)
- Telegram commands for goal management
- Agent suggests weekly plans based on commitments
- Progress tracking and alerts

**Key Decisions**:
- TBD: Telegram commands vs YAML vs both
- TBD: Weekly plans vs daily+weekly vs project-based
- TBD: Agent updates autonomously vs manual vs suggest-and-confirm

**Unlocked**:
- Long-term goal tracking
- Structured planning system
- Agent helps plan your week
- Progress monitored automatically

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
- ADR-018: Tower Deployment (to be written)

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
- ADR-019: Publishing Strategy (to be written)

---

## Phase Progress Summary

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1 — Core | ✅ DONE | 100% |
| Phase 2 — Intelligence | ✅ DONE | 100% |
| Phase 3 — Data | ✅ DONE | 100% |
| Phase 4 — Proactive | ✅ DONE | 100% |
| Phase 5 — Calendar | 📅 PLANNED | 0% |
| Phase 6 — Goals | 🎯 PLANNED | 0% |
| Phase 7 — Tower | 🖥️ PLANNED | 0% |
| Phase 8 — Publish | 📚 FUTURE | 0% |

**Overall Progress**: 50% (4/8 phases complete)

---

## Next Steps

1. **Answer three questions for Phase 6**:
   - Telegram commands vs YAML vs both?
   - Weekly plans vs daily+weekly vs project-based?
   - Agent updates autonomously vs manual vs suggest-and-confirm?

2. **Build Phase 5** (Calendar + Schedule):
   - YouTube Data API v3 integration
   - Google Calendar OAuth
   - Video metadata and scheduled videos tools

3. **Build Phase 6** (Goals + Plans):
   - Goals and milestones tables
   - Weekly planning system
   - Telegram commands for goal management

---

## Philosophy Reminder

This roadmap is not a sprint. It's a journey of building a personal AI system that:
- Costs nothing to run
- Lives on your hardware
- Knows you deeply
- Acts proactively on your behalf

Each phase unlocks new capabilities while maintaining the primitive builder identity: simple, clean, extensible, free.
