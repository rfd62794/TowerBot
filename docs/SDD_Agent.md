# Agent Software Design Document

## 1. Architecture Overview

PrivyBot's Agent is Layer 2 of the 6-layer architecture — the thinking layer. It takes user messages, calls OpenRouter LLMs, handles tool execution, injects memory context, and returns response strings. It knows nothing about Telegram or commands (that's Layer 0/1). No formatting (that's Layer 3 report.py). No direct SQLite (only through Layer 4/5 db.py).

```
bot/agent.py
  respond()                     — Main entry point, orchestrates LLM call loop
  _system_prompt()              — Builds system prompt with memories
  _chat()                       — LLM call with rotation on 429
  _rotate()                     — Dynamic free model rotation
  _execute()                    — Tool execution (registry + memory tools)
  _call()                       — Raw OpenRouter API call
  _extract_retry_after()        — Pull retry_after from 429 error body
  _assistant_tool_msg()          — Format assistant tool call message
  get_last_model()              — Return last model used for /status

bot/model_manager.py
  fetch_free_tool_models()      — Query OpenRouter /models API, cache 24h
  get_available_model()         — Best available model (skip throttled/incompatible)
  handle_429()                   — Record throttle with cooldown
  handle_success()              — Record success for model status
  get_status_report()           — Human-readable model status for /models
```

**Key Principles:**
- **Single responsibility**: Agent thinks, doesn't know about transport or formatting
- **Tool execution cycle**: Single iteration (not multi-step loop) — one LLM call, execute tools, one final LLM call
- **Model rotation**: Dynamic free model discovery with 429 cooldown tracking
- **Memory injection**: Memories surface into system prompt via list_memories()
- **Context bounding**: Last 10 messages from thread history
- **Tool registry**: TOOL_REGISTRY lookup for all 46 tools
- **Memory tools**: Separate from registry (save_memory, update_memory, retire_memory, get_memories)
- **Thread naming**: name_thread tool called after first response

## 2. Responsibilities

### Agent (bot/agent.py)
- **LLM call orchestration**: respond() coordinates LLM calls, tool execution, response formatting
- **System prompt construction**: _system_prompt() injects memories and behavior rules
- **Tool execution**: _execute() handles TOOL_REGISTRY tools and memory tools
- **Model rotation**: _rotate() tries free models on 429, skips throttled/incompatible
- **Context management**: get_context() bounds conversation history to last 10 messages
- **Thread management**: create_thread(), update_thread_active(), update_thread_name()
- **Message persistence**: add_message() stores user/assistant messages
- **Error handling**: _CreditsExhausted, _AllRateLimited, generic error fallback
- **Tool-call leak detection**: Detects raw tool-call text leaked by incompatible models

### Model Manager (bot/model_manager.py)
- **Free model discovery**: fetch_free_tool_models() queries OpenRouter /models API
- **Model caching**: Cache model list for 24h in kv_cache table
- **Throttle tracking**: handle_429() records cooldowns in model_status table
- **Success tracking**: handle_success() records successful calls
- **Model selection**: get_available_model() returns best available model
- **Incompatibility exclusion**: TOOL_INCOMPATIBLE set skips models with tool-call format issues
- **Status reporting**: get_status_report() for /models command

## 3. What It Does NOT Do

- **No Telegram knowledge**: Doesn't know about commands, users, or chat IDs
- **No formatting**: No Markdown, no HTML, no Telegram-specific formatting
- **No direct SQLite**: All DB access through infra/db layer
- **No multi-step tool loops**: Single iteration (one tool round, not recursive)
- **No streaming**: No streaming responses, full completion only
- **No image generation**: No image tools, no multimodal
- **No file operations**: No file system access
- **No network calls**: All network calls through tools or OpenRouter SDK

## 4. Key Functions and Their Roles

### Agent Functions

**respond(message, thread_id, model_key)**
- **Purpose**: Main entry point, orchestrates LLM call loop
- **Flow**:
  1. create_thread() (idempotent)
  2. add_message(thread_id, "user", message)
  3. Build messages: system prompt + get_context(thread_id, 10)
  4. _chat() with ALL_TOOLS, allow_rotation if model_key=="default"
  5. If tool_calls: _execute() each, inject results, _chat() again
  6. add_message(thread_id, "assistant", text)
  7. update_thread_active(thread_id)
- **Returns**: Response text string
- **Error handling**: _CreditsExhausted, _AllRateLimited, generic error fallback

**_system_prompt()**
- **Purpose**: Build system prompt with memories and behavior rules
- **Flow**:
  1. list_memories() from DB
  2. Format as "- [layer] key: content" lines
  3. Inject into template with rules
- **Rules**:
  - Memory rules (name_thread, save_memory, update_memory, get_memories)
  - Commitment detection (save_commitment triggers)
  - Grounding rules (web_search/wiki_lookup before factual answers)
  - Think before complex actions (think() for multi-step)
- **Returns**: System prompt string

**_chat(model, messages, tools, allow_rotation)**
- **Purpose**: LLM call with rotation on 429
- **Flow**:
  1. _call(model, messages, tools)
  2. handle_success(model)
  3. Set _last_model_used
  4. Return response, model
- **Error handling**:
  - 429: handle_429(), _rotate() if allow_rotation
  - 402: If model != default, fallback to default
  - Other: raise
- **Returns**: (response, model_used)

**_rotate(messages, tools)**
- **Purpose**: Try dynamically-discovered free models, skipping throttled/incompatible
- **Flow**:
  1. get_available_model() from model_manager
  2. If None: raise _AllRateLimited
  3. _call(fallback, messages, tools)
  4. If success: handle_success(), report("model_routed"), return
  5. If 429: handle_429() with retry_after, continue loop
  6. If other error: handle_429() with 300s cooldown, continue loop
- **Returns**: (response, model_used)

**_execute(thread_id, name, args)**
- **Purpose**: Execute tool call (registry or memory tools)
- **Flow**:
  1. TOOL_REGISTRY lookup: tool_fn = TOOL_REGISTRY[name]["fn"]
  2. Call tool_fn(**args)
  3. Validate return type (must be dict)
  4. Report event (commitment_saved, thought, tool_called, memory_saved, etc.)
  5. Memory tools: save_memory, update_memory, retire_memory, get_memories
  6. name_thread: update_thread_name()
- **Returns**: dict result
- **Error handling**: Returns error dict if tool returns None or wrong type

**_call(model, messages, tools)**
- **Purpose**: Raw OpenRouter API call
- **Parameters**: model, messages, max_tokens=8000, tools, tool_choice="auto"
- **Returns**: OpenRouter response
- **Note**: max_retries=0 in client (SDK retries add 19-23s blocking)

**_extract_retry_after(error)**
- **Purpose**: Pull retry_after_seconds from OpenRouter 429 error body
- **Returns**: float or None (fallback to 60.0)

**_assistant_tool_msg(msg)**
- **Purpose**: Format assistant tool call message for message history
- **Returns**: dict with role="assistant", tool_calls list

**get_last_model()**
- **Purpose**: Return last model used for /status command
- **Returns**: model string or "none"

### Model Manager Functions

**fetch_free_tool_models()**
- **Purpose**: Return free, tool-capable model ids
- **Flow**:
  1. Check kv_cache for cached list (24h TTL)
  2. If cached: return
  3. Query OpenRouter /models API with httpx
  4. Filter: pricing.prompt=0, pricing.completion=0, tools in supported_parameters
  5. If empty: fallback to SEED_FREE_MODELS
  6. Cache result in kv_cache
- **Returns**: list of model ids
- **Fallback**: SEED_FREE_MODELS (9 known good models)

**get_available_model()**
- **Purpose**: Best available free model, skipping throttled/incompatible
- **Flow**:
  1. fetch_free_tool_models()
  2. get_throttled_models() from DB
  3. Iterate models, skip if throttled or TOOL_INCOMPATIBLE
  4. Return first available
- **Returns**: model id or None

**handle_429(model_id, retry_after)**
- **Purpose**: Record throttle with cooldown
- **Behavior**: record_throttle(model_id, retry_after) in model_status table

**handle_success(model_id)**
- **Purpose**: Record successful call
- **Behavior**: record_success(model_id) in model_status table

**get_status_report()**
- **Purpose**: Human-readable model status for /models command
- **Flow**:
  1. fetch_free_tool_models()
  2. get_throttled_models()
  3. get_model_status_all()
  4. Format with throttled/available indicators
- **Returns**: Formatted string

## 5. Patterns and Conventions

### Tool Execution Cycle
- **Single iteration**: One LLM call, execute tools, one final LLM call (not recursive)
- **Tool registry**: TOOL_REGISTRY lookup for all 46 tools
- **Memory tools**: Separate from registry (save_memory, update_memory, retire_memory, get_memories)
- **name_thread**: Called after first response in new thread
- **Result injection**: Tool results injected as "tool" role messages

### Model Rotation
- **Dynamic discovery**: fetch_free_tool_models() queries OpenRouter /models API
- **Cooldown tracking**: handle_429() records cooldowns in model_status table
- **Incompatibility exclusion**: TOOL_INCOMPATIBLE set skips models with tool-call format issues
- **Fallback chain**: default → free model rotation → _AllRateLimited
- **Seed models**: SEED_FREE_MODELS used if API call fails

### Memory Injection
- **System prompt**: Memories injected via list_memories() in _system_prompt()
- **Format**: "- [layer] key: content" lines
- **Timing**: Called on every respond() (fresh memories each request)
- **Memory tools**: save_memory, update_memory, retire_memory, get_memories available to agent

### Context Management
- **History bounding**: get_context(thread_id, 10) — last 10 messages
- **Thread persistence**: create_thread(), add_message(), update_thread_active()
- **Thread naming**: name_thread tool called after first response

### Error Handling
- **429 handling**: handle_429() with retry_after, model rotation
- **402 handling**: Fallback to default model if not already default
- **All rate-limited**: _AllRateLimited exception, user message
- **Credits exhausted**: _CreditsExhausted exception, user message
- **Generic error**: Catch-all, user message

### Tool-Call Leak Detection
- **Detection**: Check for raw tool-call markers in response text
- **Markers**: Angle brackets, function, backticks
- **Logging**: Warning logged with model name and leaked text
- **Purpose**: Identify incompatible models for TOOL_INCOMPATIBLE set

## 6. Data Flow

### Response Flow
```
User message via Telegram
    ↓
transport.py (Layer 0) → router.py (Layer 1)
    ↓
agent.respond(message, thread_id, model_key)
    ↓
create_thread() / add_message(user)
    ↓
_system_prompt() → list_memories() → inject into system prompt
    ↓
get_context(thread_id, 10) → last 10 messages
    ↓
_chat(model, messages, ALL_TOOLS, allow_rotation)
    ↓
_call() → OpenRouter API
    ↓
If tool_calls:
    ↓
_execute() each tool
    ↓
TOOL_REGISTRY lookup → tool_fn(**args)
    ↓
Report event (tool_called, memory_saved, etc.)
    ↓
Inject results as "tool" role messages
    ↓
_chat(model, messages, None) → final response
    ↓
add_message(assistant, text)
    ↓
update_thread_active()
    ↓
Return text to report.py (Layer 3)
```

### Model Rotation Flow
```
_chat() with 429 error
    ↓
handle_429(model, retry_after)
    ↓
_rotate(messages, tools)
    ↓
get_available_model() → fetch_free_tool_models()
    ↓
Check throttled models (get_throttled_models)
    ↓
Check TOOL_INCOMPATIBLE
    ↓
_call(fallback, messages, tools)
    ↓
If success: handle_success(), report("model_routed"), return
    ↓
If 429: handle_429(), continue loop
    ↓
If other error: handle_429(300s), continue loop
    ↓
If None available: raise _AllRateLimited
```

### Memory Injection Flow
```
respond() called
    ↓
_system_prompt()
    ↓
list_memories() from DB
    ↓
Format as "- [layer] key: content"
    ↓
Inject into system prompt template
    ↓
LLM sees memories in context
    ↓
Agent can call save_memory/update_memory/get_memories
```

### Tool Execution Flow
```
LLM returns tool_calls
    ↓
_execute(thread_id, name, args)
    ↓
TOOL_REGISTRY lookup
    ↓
tool_fn(**args)
    ↓
Validate return type (must be dict)
    ↓
Report event (tool_called, memory_saved, etc.)
    ↓
Return dict result
    ↓
Inject as "tool" role message
    ↓
LLM sees tool result in next call
```

## 7. Error Handling Contract

### Agent Layer
- **429 errors**: handle_429() with retry_after, model rotation via _rotate()
- **402 errors**: Fallback to default model if not already default
- **All rate-limited**: _AllRateLimited exception, return user message
- **Credits exhausted**: _CreditsExhausted exception, return user message
- **Generic errors**: Catch-all exception, report("error"), return user message
- **Tool errors**: _execute() returns error dict if tool returns None or wrong type
- **Thread exists**: create_thread() try/except, pass if already exists
- **JSON decode errors**: tool_call arguments default to {} on JSONDecodeError

### Model Manager Layer
- **API failures**: fetch_free_tool_models() falls back to SEED_FREE_MODELS
- **No available models**: get_available_model() returns None, raises _AllRateLimited
- **Invalid models**: handle_429() with 300s cooldown for non-429 errors
- **Cache failures**: get_cached_model_list() returns None, triggers API call

### Tool Execution
- **None returns**: Return error dict "Tool {name} returned None"
- **Wrong type returns**: Return error dict "Tool {name} returned unexpected type: {type}"
- **Missing args**: Memory tools return error dict if required args missing
- **Unknown tools**: Return error dict "unknown tool {name}"

## 8. Testing Strategy

### Test Coverage
- **scripts/verify.py**: 204/204 tests pass
- **Model tests**: test_models.py validates free models for tool calling
- **Agent tests**: No dedicated agent tests (tested via integration)
- **Model manager tests**: No dedicated model_manager tests (tested via integration)

### Test Categories
- **Model validation**: test_models.py runs all free models through tool calling test
- **Tool registry**: TOOL_REGISTRY validated via tool tests
- **Memory tools**: Tested via personal tasks tests
- **Integration**: Full agent flow tested via manual Telegram interaction

### Test Execution
- **Command**: `uv run python scripts/verify.py`
- **Pass criteria**: 204/204 tests pass
- **Deploy gate**: Must pass before GitHub commit

## 9. Related ADRs
- ADR-001: Layered Architecture
- ADR-004: Memory System
- ADR-005: Focus Injection
- ADR-006: Commitment Tracking
