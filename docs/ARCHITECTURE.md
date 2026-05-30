# PrivyBot Architecture

PrivyBot is a personal AI assistant built with a layered architecture. Each layer has a single responsibility and clear import boundaries.

## Architecture Decision Records (ADRs)

This document is supplemented by ADRs that capture key architectural decisions:

- [ADR-001: API/Tool Separation Pattern](adr/ADR-001.md) — Separation between API clients and tool logic
- [ADR-002: Tool Registry Pattern](adr/ADR-002.md) — Centralized tool discovery via TOOL_REGISTRY
- [ADR-003: Caching Strategy](adr/ADR-003.md) — SQLite-based caching with per-tool TTL
- [ADR-004: Layered Architecture](adr/ADR-004.md) — Six-layer architecture with strict import boundaries
- [ADR-005: Model Routing Strategy](adr/ADR-005.md) — OpenRouter with dynamic model discovery and throttle tracking
- [ADR-006: Autonomous Memory Management](adr/ADR-006.md) — Agent-driven memory with transparency
- [ADR-007: SQLite as Persistence Layer](adr/ADR-007.md) — Single SQLite database for all state
- [ADR-008: Telegram as Primary Interface](adr/ADR-008.md) — Telegram Bot API with polling and single-user gate
- [ADR-009: Python 3.12 + uv](adr/ADR-009.md) — Python 3.12 due to 3.14 TLS bug, uv for dependency management
- [ADR-010: Context Window Strategy](adr/ADR-010.md) — 10-message sliding window with thread isolation
- [ADR-011: Tool Architecture](adr/ADR-011.md) — Tools as plug-ins with TOOL_REGISTRY pattern
- [ADR-012: Morning Briefing Design](adr/ADR-012.md) — Template-based briefing with LLM anomaly analysis
- [ADR-023: DBManager](adr/ADR-023.md) — Single owner of database access with retry logic
- [ADR-024: fetch_url Browser Tool](adr/ADR-024.md) — Browser tool for reading full web page content
- [ADR-025: think Scratchpad Tool](adr/ADR-025.md) — Scratchpad tool for context continuity
- [ADR-026: RateLimitManager Layer](adr/ADR-026.md) — API rate limit tracking and quota awareness (planned)

## Layer Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 0: Transport (transport.py)                           │
│ Telegram Bot API integration, message handling, retries     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Router (router.py)                                 │
│ Command parsing, thread management, delegation             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Agent (agent.py)                                   │
│ OpenRouter calls, tool execution, memory injection          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Report (report.py)                                 │
│ Event logging, Telegram notifications                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Memory (memory.py)                                 │
│ Agent memory tools, TOOL_DEFINITIONS                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Database (core/db/)                                │
│ SQLite persistence, schema, migrations                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 5b: DBManager (core/db/manager.py)                   │
│ Single owner of database access, retry logic, WAL mode      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 6: Tool Logic (tools/*.py)                           │
│ Business logic, scoring, verdicts, result shaping          │
│ BaseTool: success(), error(), stale_notice()               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 7: CacheManager (core/cache.py)                       │
│ Single owner of cache behavior, TTL policy, stale fallback  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 7b: RateLimitManager (core/rate_limits.py)            │
│ API rate limit tracking, quota awareness, call logging      │
│ (planned, not yet built)                                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 8: API Clients (tools/api/*.py)                       │
│ Raw HTTP calls, auth, response parsing                      │
│ BaseAPIHandler: CACHE_PREFIX, call(), hash()                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 9: Meta Tools (tools/meta.py)                         │
│ Scratchpad tools, no API calls, no caching                  │
│ think() — context continuity across model switches          │
└─────────────────────────────────────────────────────────────┘
```

## Import Rules

- **Layer N** can import from **Layer N+1** (lower layers)
- **Layer N** cannot import from **Layer N-1** (higher layers)
- No circular imports
- Each layer owns its domain completely

## Layer Details

### Layer 0: Transport (`transport.py`)

**Responsibility:** Telegram Bot API integration

- Builds the PTB application
- Handles incoming messages
- Sends replies with retry logic (Windows TLS resilience)
- No business logic — only transport

**Imports:**
- `router.route` (Layer 1)
- `report.report` (Layer 3) for error reporting

**Never imports:**
- `agent`, `memory`, `db` (business logic layers)

### Layer 1: Router (`router.py`)

**Responsibility:** Command parsing and delegation

- Parses incoming text for commands (`/think`, `/claude`, `/new`, `/memories`, `/models`, `/status`)
- Manages thread-per-chat mapping
- Delegates to `agent.respond()` for AI responses
- Returns status reports for `/models` and `/status`

**Imports:**
- `agent.respond`, `agent.get_last_model` (Layer 2)
- `db.create_thread`, `db.list_memories`, `db.list_threads` (Layer 5)
- `report.report` (Layer 3)
- `model_manager.get_status_report`, `model_manager.get_throttled_models` (model_manager)

**Never imports:**
- `transport` (Layer 0) — no Telegram knowledge
- `memory` (Layer 4) — tools are called by agent, not router

### Layer 2: Agent (`agent.py`)

**Responsibility:** Thinking and tool execution

- Calls OpenRouter API with messages and tools
- Handles tool calls (name_thread, save_memory, etc.)
- Injects memory context into system prompt
- Manages model rotation on 429 errors
- Tracks last model used for `/status`

**Imports:**
- `db.get_context`, `db.add_message`, `db.update_thread_name`, etc. (Layer 5)
- `memory.TOOL_DEFINITIONS`, `memory.tool_*` (Layer 4)
- `report.report` (Layer 3)
- `model_manager.get_available_model`, `model_manager.handle_429`, etc. (model_manager)

**Never imports:**
- `transport`, `router` (Layers 0-1) — no Telegram or command knowledge

### Layer 3: Report (`report.py`)

**Responsibility:** Event logging and notifications

- Logs key bot events (thread_new, memory_saved, model_routed, error)
- Sends Telegram notifications for important events
- Markdown-safe message formatting

**Imports:**
- None (pure event layer, injected send function at startup)

**Never imports:**
- `transport`, `router`, `agent`, `memory`, `db` (no business logic)

### API Layer (`tools/api/`)

**Responsibility:** External service clients

- HTTP communication with external APIs (YouTube, Steam, Gmail, Google Calendar, etc.)
- Authentication and credential management
- Request/response parsing and normalization
- API-specific error handling and retry logic
- Cached API call pattern via `_base.py`

**Files:**
- `_base.py` — `cached_api_call()`, `stale_notice()`, `make_params_hash()`
- `youtube_api.py` — YouTube Analytics + Data API
- `steam_api.py` — Steam Web API
- `steamspy_api.py` — SteamSpy API
- `itad_api.py` — IsThereAnyDeal API
- `gmail_api.py` — Gmail API (dual account support)
- `google_calendar_api.py` — Google Calendar API
- `google_tasks_api.py` — Google Tasks API
- `weather_api.py` — Open-Meteo weather API
- `ddg_api.py` — DuckDuckGo search API
- `wikipedia_api.py` — Wikipedia API
- `reddit_api.py` — Reddit API

**Imports:**
- `core.db.cache` — for cache functions
- External libraries: `googleapiclient`, `requests`, `httpx`

**Never imports:**
- `tools/` (tool layer) — no business logic
- `core/` (core layer) — no bot infrastructure

### Tool Layer (`tools/`)

**Responsibility:** Business logic and tool implementations

- Domain-specific processing and data transformation
- Scoring, ranking, and verdict generation
- Fuzzy matching and search logic
- Combining data from multiple API calls
- Tool registration in `__init__.py` (TOOL_REGISTRY)

**Files:**
- `__init__.py` — TOOL_REGISTRY (single source of truth)
- `calendar.py` — Calendar tools (get_today_schedule, get_upcoming_events)
- `gmail.py` — Gmail tools (get_inbox_summary, search_email, check_sender)
- `personal.py` — Personal task tools (add_personal_task, complete_personal_task)
- `sync_tasks.py` — Google Tasks sync orchestration
- `goals.py` — Goals and plans tools
- `youtube/channel.py` — Channel metrics tools
- `youtube/discovery.py` — Content discovery tools
- `youtube/videos.py` — Video analytics tools
- `games.py` — Game metrics tools
- `search.py` — Search tools (web, news, wiki, reddit)

**Imports:**
- `tools/api/*` — API clients
- `core.db.*` — database functions
- `core.db.cache` — cache functions

**Never imports:**
- `core/agent`, `core/router`, `core/transport` — no bot infrastructure

### Core Layer (`core/`)

**Responsibility:** Bot infrastructure

- Agent logic (OpenRouter calls, tool execution)
- Router logic (command parsing, thread management)
- Scheduler logic (heartbeat, morning briefing, proactive checks)
- Model management (model discovery, throttle tracking)
- Report layer (event logging, notifications)

**Files:**
- `agent.py` — OpenRouter client, tool execution
- `router.py` — Command parsing, delegation
- `scheduler.py` — Heartbeat, morning briefing, proactive scheduling
- `model_manager.py` — Model discovery, throttle tracking
- `report.py` — Event logging, notifications
- `transport.py` — Telegram Bot API integration

**Imports:**
- `tools/` — tool functions
- `core.db/*` — database functions

**Never imports:**
- `tools/api/` — API layer accessed via tools only

### DB Layer (`core/db/`)

**Responsibility:** SQLite persistence

- Schema definition and migrations
- CRUD functions for all tables
- Cache management (tool_cache, preload_log)
- Thread-safe connection management
- Pure database — no business logic

**Files:**
- `schema.py` — Schema, migrations, _exec, WAL mode
- `cache.py` — Cache functions (get_stale_cached_result, record_preload_result)
- `memory.py` — Memory CRUD
- `threads.py` — Thread CRUD
- `messages.py` — Message CRUD
- `personal_tasks.py` — Personal tasks CRUD
- `history.py` — Historical data (channel, video, game, weather)
- `deployments.py` — Deploy history
- `goals.py` — Goals, milestones, tasks, weekly plans
- `queue.py` — Task queue

### Layer 5b: DBManager (`core/db/manager.py`)

**Responsibility:** Single owner of database access

- Centralized database access with retry logic
- Exponential backoff for lock errors (0.1s, 0.2s, 0.4s, 0.8s, 1.6s)
- WAL mode coordination
- Future: connection pooling, query logging, metrics

**Key Methods:**
- `db.exec(sql, params, commit)` — Execute with automatic retry
- `db.exec_many(sql, params_list, commit)` — Batch execution
- `db.get_connection()` — Get current connection

**Imports:**
- `core.db.schema._exec` (internal only)

**Never imports:**
- Business logic layers

### Layer 6: Tool Logic (`tools/*.py`)

**Responsibility:** Business logic, result shaping

- Tool implementations (calendar, gmail, personal, goals, etc.)
- Business logic, scoring, verdicts
- Result shaping for agent consumption
- Side effects (history writes, task updates)

**BaseTool Pattern:**
- `success(data, stale_result)` — Standard success return with `ok=True`, `stale_notice`
- `error(message, code)` — Standard error return with `ok=False`, `error`, `error_code`
- `stale_notice(result)` — Convenience wrapper for cache.stale_notice()
- Internal key stripping — removes `_stale`, `_cached_at` from returned data

**Return Shape:**
```python
# Success
{
    "ok": True,
    "stale_notice": None,  # or string if stale
    "temp_f": 83.6,        # tool-specific data
    ...
}

# Error
{
    "ok": False,
    "error": "Service unavailable",
    "error_code": "api_failed",
    "stale_notice": None
}
```

**Imports:**
- `tools.api.*` (Layer 8)
- `core.cache` (Layer 7)
- `core.db.*` (Layer 5/5b)

**Never imports:**
- `transport`, `router`, `agent` (higher layers)

### Layer 7: CacheManager (`core/cache.py`)

**Responsibility:** Single owner of cache behavior

- TTL policy — canonical source of truth for all cache TTLs
- Staleness budget — acceptable stale age per tool
- Fresh hit detection, stale fallback logic
- Preload coordination
- Cache invalidation

**Key Methods:**
- `cache.call(key, params_hash, live_fn, stale_ok)` — Main entry point for API calls
- `cache.get(key, params_hash)` — Fresh cache hit only
- `cache.get_or_stale(key, params_hash)` — Fresh first, stale if expired
- `cache.set(key, params_hash, data)` — Store with TTL from policy
- `cache.stale_notice(result)` — Human-readable staleness string
- `cache.invalidate(key, params_hash)` — Clear cached data
- `cache.status()` — Health of all cached tools
- `cache.preload(tasks)` — Warm cache from task list

**TTL Policy:**
- `weather`: 3600s (1h)
- `gmail_personal`: 300s (5min)
- `youtube_channel`: 86400s (24h)
- `steam_library`: 86400s (24h)
- etc. (see `CacheManager.TTL`)

**Imports:**
- `core.db.cache` (Layer 5) — storage functions only

**Never imports:**
- API layers, tool layers

### Layer 7b: RateLimitManager (`core/rate_limits.py`)

**Responsibility:** API rate limit tracking and quota awareness

- Track API rate limits per service
- Log all API calls for usage analysis
- Provide quota visibility in `/status` command
- Proactive rate limit awareness before 429 errors
- Graceful degradation when approaching limits

**Planned Features:**
- DB tables: `api_rate_limits`, `api_call_log`
- Singleton: `rate_limits = RateLimitManager()`
- BaseAPIHandler integration before live calls
- Known limits: YouTube (10k units/day), Gmail (5 req/sec), Steam (200 req/5min), etc.

**Status:** Planned (not yet built)

**Imports:**
- `core.db.*` (Layer 5) — for rate limit storage

**Never imports:**
- API layers, tool layers

### Layer 8: API Clients (`tools/api/*.py`)

**Responsibility:** Raw HTTP calls only

- Authentication
- Request formation
- Response parsing
- Error raising (typed)
- No caching
- No business logic

**BaseAPIHandler Pattern:**
- `CACHE_PREFIX` — Must be set by subclass (validated at runtime)
- `cache_key(suffix)` — Namespaced cache key generation
- `call(suffix, params_hash, live_fn, stale_ok)` — Delegates to CacheManager
- `hash(*args, **kwargs)` — Convenience wrapper for cache.hash()
- `_get_client()` — Abstract method for credential loading

**Subclass Example:**
```python
class WeatherAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "weather"

    def _get_client(self):
        return None  # Open-Meteo needs no auth

    def get_current_weather(self) -> dict:
        def _live():
            # HTTP call
            return {"temp_f": ..., ...}
        return self.call("current", self.hash(), _live)
```

**Imports:**
- `core.cache` (Layer 7)
- External HTTP libraries (requests, httpx)

**Never imports:**
- Tool layers, business logic

### Layer 9: Meta Tools (`tools/meta.py`)

**Responsibility:** Scratchpad tools for agent reasoning

- Simple functions with no API calls
- No caching, no staleness, no side effects
- Context continuity across model switches
- think() — visible reasoning before complex actions

**Why not BaseTool:**
- BaseTool exists for API-calling tools with caching
- think has no network, no cache, no stale data
- Forcing BaseTool adds noise without benefit

**Context Continuity:**
- think() creates conversation history record
- Model-agnostic — any model sees past thoughts
- Throttled model switches preserve context
- New model reads thoughts and continues plan

**Imports:**
- None (pure functions)

**Never imports:**
- Any other layers

### Model Manager (`model_manager.py`)

**Responsibility:** Dynamic model discovery and throttle tracking

- Fetches free, tool-capable models from OpenRouter
- Caches model list for 24h
- Tracks 429 cooldowns per model in SQLite
- Provides human-readable status for `/models` command

**Imports:**
- `db.record_throttle`, `db.record_success`, `db.get_throttled_models`, etc. (Layer 5)

**Never imports:**
- `transport`, `router`, `agent`, `report`, `memory` (Layers 0-4)

## Tool Plug-in Pattern

Tools are defined in `memory.py` and executed by `agent.py`:

1. **Define tool schema** in `TOOL_DEFINITIONS` (OpenAI function format)
2. **Implement tool function** that calls `db` functions
3. **Agent handles execution** via `_execute()` when OpenRouter returns tool_calls
4. **Tool results** are fed back to the model for completion

Example tool flow:
```
User message → Agent (with tools) → OpenRouter → tool_calls → Agent._execute() → Tool function → db.save_memory() → Result → OpenRouter → Final response
```

## Adding a New Layer

To add a new layer (e.g., a caching layer between agent and database):

1. Create the new file (e.g., `cache.py`)
2. Define the layer's single responsibility
3. Import only from layers below it
4. Export functions for layers above it
5. Update import chains in affected layers
6. Update this document

**Example:** Adding a cache layer at Layer 4.5:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Memory (memory.py)                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 4.5: Cache (cache.py) ← NEW                           │
│ In-memory caching, TTL management                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Database (db.py)                                   │
└─────────────────────────────────────────────────────────────┘
```

- `memory.py` imports from `cache.py` instead of `db.py`
- `cache.py` imports from `db.py`
- Cache misses fall through to database
- Cache hits return immediately

## Key Design Principles

1. **Single Responsibility:** Each layer does one thing well
2. **Clear Boundaries:** Import only from lower layers
3. **Testability:** Layers can be tested in isolation
4. **Replaceability:** Swap a layer without affecting others
5. **No Circular Dependencies:** Strict top-down import flow

## Data Flow

```
Telegram Message
    ↓
transport.handle_message()
    ↓
router.route()
    ↓
agent.respond()
    ↓
OpenRouter API (with tools)
    ↓
agent._execute() → memory.tool_*() → db.*()
    ↓
agent.respond() (with tool results)
    ↓
transport.reply_text()
    ↓
Telegram User
```

## Startup Sequence

1. `privybot.py` validates environment variables and database
2. `db.init_db()` creates schema if needed
3. `transport.build_app()` creates PTB application
4. `report.init_report()` injects Telegram send function
5. `app.run_polling()` starts the bot
