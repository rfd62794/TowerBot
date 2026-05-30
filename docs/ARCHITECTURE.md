# PrivyBot Architecture

PrivyBot is a personal AI assistant built with a layered architecture. Each layer has a single responsibility and clear import boundaries.

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
│ Tool definitions, tool implementations                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Database (db.py)                                   │
│ SQLite operations, schema, persistence                      │
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

### Layer 4: Memory (`memory.py`)

**Responsibility:** Tool definitions and implementations

- Defines `TOOL_DEFINITIONS` for OpenRouter function calling
- Implements tool functions: `save_memory`, `update_memory`, `retire_memory`, `get_memories`, `name_thread`
- Calls `db` functions for persistence

**Imports:**
- `db.save_memory`, `db.update_memory`, `db.retire_memory`, `db.get_memories`, `db.update_thread_name` (Layer 5)

**Never imports:**
- `transport`, `router`, `agent`, `report` (Layers 0-3)

### Layer 5: Database (`db.py`)

**Responsibility:** SQLite persistence

- Defines schema (threads, messages, memory, model_status, kv_cache)
- Provides CRUD functions for all tables
- Thread-safe connection management
- Pure database — no business logic

**Imports:**
- None (pure SQLite, no external services)

**Never imports:**
- Any other layer (bottom of the stack)

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
