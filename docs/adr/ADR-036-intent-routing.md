# ADR-036: Intent-Aware Routing — Ollama as Classifier, Focused Tool Sets per Route

**Status:** Accepted  
**Date:** May 2026  
**Context:** PrivyBot model routing architecture  
**Deciders:** Robert Floyd Dugger  

---

## Context

PrivyBot's current routing passes `ALL_TOOLS` (30+ tool definitions, ~10KB of JSON) to
every LLM call regardless of what the user asked. This causes three compounding problems:

1. **gemma3:4b tool calling is unreliable at scale.** Benchmarks score it 2.0/5 for
   tool calling with state management loops and failures. With 22+ tools the accuracy
   degrades further. Passing 30+ tools to it caused consistent 400 Bad Request errors
   from Ollama's `/api/chat` endpoint.

2. **OpenRouter models with 30+ tools make more erroneous calls.** Irrelevant tools
   are noise that increases hallucinated tool selections. Focused tool sets (3-7
   relevant tools) produce cleaner, more accurate responses.

3. **Every message — including simple conversational replies — incurs OpenRouter API
   cost and latency.** A "thanks" or "what time is it?" query hits the same path as
   "pull my calendar and emails." The `chat` case should cost nothing and take under
   one second.

### What gemma3:4b is actually good at

Classification tasks: deterministic JSON output, bounded output space, no multi-turn
state management. Routing is exactly this. The model classifies intent into a known
set of route names and returns a single JSON object. This is reliable where tool
calling is not.

---

## Decision

**Ollama (gemma3:4b) acts as the intent classifier and router, not as a tool executor.**

Every plain-text user message passes through a `classify()` call to Ollama first.
Ollama returns a route decision. The agent then selects a focused tool subset and
the appropriate model for that route. Slash commands bypass classification entirely.

### Route Table

Defined in `config/routes.yaml`. Each route specifies the target model and the
exact tool names it may use.

```yaml
routes:
  chat:
    model: ollama/gemma3:4b
    tools: []
    description: "General conversation, greetings, simple questions requiring no data"

  calendar:
    model: openrouter/free
    tools: [get_today_schedule, get_upcoming_events, check_availability, save_commitment]
    description: "Schedule, events, availability, commitments"

  email:
    model: openrouter/free
    tools: [get_inbox_summary, search_email, check_sender, read_email]
    description: "Inbox, messages, email search"

  voidrift:
    model: openrouter/free
    tools: [get_itch_stats, reddit_search, get_recent_commits, get_content_recommendations]
    description: "VoidDrift game stats, Reddit mentions, commits, content"

  youtube:
    model: openrouter/free
    tools: [get_youtube_stats, get_top_videos, get_video_analytics,
            get_retention_curve, get_daily_views, get_audience_demographics]
    description: "YouTube channel stats, video performance, analytics"

  goals:
    model: openrouter/free
    tools: [get_goals_list, get_goal_detail, get_current_plan, get_tasks_today,
            add_new_task, update_task, get_upcoming_tasks]
    description: "Goals, tasks, milestones, weekly planning"

  memory:
    model: openrouter/free
    tools: [save_memory, get_memories, update_memory, retire_memory]
    description: "Save or retrieve memories and personal context"

  code:
    model: ollama/qwen2.5-coder:7b
    tools: [read_local_file, list_local_dir, search_local_code,
            audit_repo_compliance, analyze_code_quality, find_opportunities,
            read_current_state, generate_directive]
    description: "Code analysis, repo inspection, directive generation"

  search:
    model: openrouter/free
    tools: [web_search, wiki_lookup, news_search, fetch_url]
    description: "Web search, Wikipedia, news, URL fetch"

  steam:
    model: openrouter/free
    tools: [get_game_metrics, get_installed_games, get_sale_info]
    description: "Steam games, pricing, metrics"

  openagent:
    model: openrouter/free
    tools: [get_pypi_stats, run_openagent]
    description: "OpenAgent PyPI stats and directive generation"

  think:
    model: claude
    tools: []
    description: "Complex reasoning, architecture planning, multi-step analysis"

  system:
    model: openrouter/free
    tools: [get_system_resources, get_ollama_loaded, get_ollama_model_sizes,
            check_ollama_health, get_daily_cost]
    description: "System resources, Ollama status, budget tracking"
```

### Classification Prompt

Sent to `ollama/gemma3:4b` via `classify()` — no tool definitions, no system context,
minimal tokens:

```
Classify the user message into one or more routes.
Return ONLY valid JSON matching: {"routes": ["route1", "route2"]}

Valid routes: chat, calendar, email, voidrift, youtube, goals, memory,
              code, search, steam, openagent, think, system

Rules:
- Use "chat" only when no external data is needed
- Multiple routes when the message clearly spans two domains
- Maximum two routes per message
- If uncertain between "chat" and a data route, prefer the data route

Message: {user_message}
```

### Call Flow

```
User plain-text message
  → classify(message) via ollama/gemma3:4b (~0.5s)
  → parse routes from JSON response
  → merge tool subsets for all returned routes
  → call target model with focused tool set
  → return response

If route == ["chat"]:
  → respond directly from ollama/gemma3:4b
  → zero OpenRouter cost, sub-second

If route == ["code"]:
  → OllamaSwapManager unloads gemma3:4b, loads qwen2.5-coder:7b
  → ~10-20s VRAM swap (covered by _thinking_thread UX)
  → respond from code model with code tools only
```

### Slash Command Coexistence

Slash commands bypass `classify()` entirely. The existing router.py handles them
before the message reaches `respond()`. This is a hard boundary:

```
/think   → model=MODELS["claude"],   tools=[]         (unchanged)
/claude  → model=MODELS["claude"],   tools=[]         (unchanged)
/new     → thread reset              (unchanged)
/status  → system info               (unchanged)
plain msg → classify() → route → respond()
```

No slash command touches `router_ai.py`. No plain message bypasses it.

### Autonomous Task Routing

Autonomous tasks call `agent.respond()` directly with task-specific prompts. They
bypass `classify()` and specify their own tool requirements in the task prompt.
The `[AUTONOMOUS MODE]` guard already separates these from user messages.

---

## Risks and Mitigations

### 1. Classification failure on ambiguous messages

*Risk:* "What should I focus on?" classifies as `chat` and gets a generic answer
instead of pulling goals and calendar data.

*Mitigation:* Low-confidence fallback rule in the classification prompt: prefer the
data route over `chat` when uncertain. If `["chat"]` is returned but the message
contains any of: `should`, `what about`, `how is`, `update`, `status` — escalate
to `["goals"]` or the full tool set. Implement as a post-classification heuristic
in `router_ai.py`, not in the Ollama prompt.

### 2. qwen2.5-coder:7b VRAM swap latency

*Risk:* Unloading gemma3:4b (3.5GB) and loading qwen2.5-coder:7b (4GB) takes
10-20 seconds. User expects a response.

*Mitigation:* `_thinking_thread` already covers this with rotating status messages.
The code route should be reserved for explicit coding requests ("analyze my repo",
"what's the directive for X") — not casual mentions of code. Classification prompt
should require strong signal before routing to `code`.

### 3. JSON output reliability

*Risk:* gemma3:4b hallucinate outside the route name set or produce malformed JSON.

*Mitigation:* Strict parsing in `router_ai.py`:
```python
def parse_routes(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw.strip())
        routes = parsed.get("routes", [])
        valid = [r for r in routes if r in VALID_ROUTES]
        return valid if valid else ["chat"]
    except Exception:
        return ["chat"]   # safe default, never crash
```
Unknown route names are silently dropped. Empty or invalid result defaults to `chat`.

### 4. Route table maintenance drift

*Risk:* A new tool is added to `TOOL_REGISTRY` but not assigned to any route, making
it silently unreachable through normal conversation.

*Mitigation:* A required test in `tests/test_routes.py`:
```python
def test_all_registry_tools_have_a_route():
    all_tool_names = set(TOOL_REGISTRY.keys())
    routed_tools = set()
    for route in ROUTES.values():
        routed_tools.update(route.get("tools", []))
    unreachable = all_tool_names - routed_tools
    assert not unreachable, f"Tools not in any route: {unreachable}"
```
This test fails as soon as a tool is added without a route assignment. Cannot be
skipped without explicit justification.

---

## Consequences

**Positive:**
- gemma3:4b used for what it does well (classification), not what it fails at (tool calling)
- OpenRouter receives 3-7 focused tools instead of 30+ — fewer erroneous calls
- `chat` route costs zero, responds in under 1 second on GPU
- `code` route uses the correct specialized model (qwen2.5-coder:7b)
- `think` route preserves the Claude path for complex reasoning
- Tool coverage enforced by test — drift caught immediately

**Negative:**
- Classification adds ~0.5s latency to every message
- `code` route adds 10-20s VRAM swap latency
- Route table is a new maintenance surface (mitigated by test)
- Multi-intent queries (2 routes) merge tool sets — still bounded, not 30+

**Neutral:**
- Slash commands unchanged — existing behavior preserved
- Autonomous tasks unchanged — bypass classify()
- Morning briefing unchanged — calls tools directly without routing

---

## Implementation Sequence

Build in this order. Each step is independently testable.

**Step 1:** `config/routes.yaml` — route definitions only, no code
- Test: `test_all_registry_tools_have_a_route()` passes

**Step 2:** `bot/router_ai.py` — `classify(message)` function
- Calls `ollama_api.classify()` (new method, no tools in payload)
- `parse_routes()` with strict fallback
- Test: mock Ollama, verify parse_routes handles malformed JSON

**Step 3:** `api/local/ollama_api.py` — `classify()` method
- Lightweight prompt, returns raw string
- No tool definitions in payload
- No `_check_vram()` call — classification is text-only, always fits

**Step 4:** `agent.py` — update `respond()` to call `router_ai.classify()` first
- Only for plain-text messages (slash commands already handled by router.py)
- Select tools and model from route
- Remaining call chain unchanged

**Step 5:** Tests
- `test_routes.py` — coverage invariant
- `test_router_ai.py` — classification, parsing, fallbacks
- `test_agent_routing.py` — end-to-end flow with mocked classify()

Locked. Do not modify `agent.py` until Steps 1-3 are complete and tested.

---

*RFD IT Services Ltd. | PrivyBot | ADR-036 | May 2026*
