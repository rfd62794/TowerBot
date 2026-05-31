# Tools Software Design Document

## 1. Architecture Overview

PrivyBot's tools system is organized into two distinct layers with clear separation of concerns:

```
tools/
  content/                ← Content tools (YouTube channel, videos, discovery)
    channel.py            ← Channel metrics tools
    discovery.py          ← Traffic sources, search terms
    videos.py             ← Video analytics, retention

  games/                  ← Game tools
    metrics.py            ← Game metrics, installed games, sale info
    recommendations.py    ← Content recommendations

  search/                 ← Search tools
    search_tools.py       ← Web, news, wiki, reddit, weather, fetch_url

  productivity/           ← Productivity tools
    calendar.py           ← Google Calendar tools
    goals.py              ← Goals, plans, tasks, commitments
    personal.py           ← Personal tasks (reminders, to-dos)
    sync.py               ← Google Tasks sync

  communication/          ← Communication tools
    gmail.py              ← Gmail tools (dual account)

  meta/                   ← Meta tools
    meta.py               ← think() scratchpad

  registry.py             ← TOOL_REGISTRY (single source of truth)

api/
  google/                 ← Google APIs
    youtube_api.py        ← YouTube Analytics + Data API
    gmail_api.py          ← Gmail API (dual account)
    calendar_api.py       ← Google Calendar API
    tasks_api.py          ← Google Tasks API

  steam/                  ← Steam APIs
    steam_api.py          ← Steam Web API
    steamspy_api.py       ← SteamSpy API
    itad_api.py           ← IsThereAnyDeal API
    catalog_api.py        ← Steam catalog resolution

  web/                    ← Web APIs
    ddg_api.py            ← DuckDuckGo Search API
    wikipedia_api.py      ← Wikipedia API
    reddit_api.py         ← Reddit API
    fetch_api.py          ← Browser tool (requests + BeautifulSoup)

  weather/                ← Weather API
    weather_api.py        ← Open-Meteo Weather API

  _handler.py             ← BaseAPIHandler, BaseTool base classes
```

**Key Principles:**
- API Layer: Knows how to talk to external services
- Tool Layer: Knows what to do with the data
- Registry: Single source of truth for tool discovery
- BaseAPIHandler: Enforces cache + rate limit patterns
- BaseTool: Enforces return shape contract

**Data Flow:**
```
Agent → Tool Registry → Tool Function → API Handler → External Service
         (definition)    (business logic)   (BaseAPIHandler)
                           ↓
                    CacheManager
                    RateLimitManager
```

## 2. Directory Structure

### Tool Layer (`tools/`)

**content/** — YouTube content tools
- `channel.py` — Channel metrics, daily views, demographics, device breakdown, geographic breakdown
- `videos.py` — Top videos, video analytics, retention curve
- `discovery.py` — Traffic sources, search terms

**games/** — Game tools
- `metrics.py` — Game metrics, installed games, sale info
- `recommendations.py` — Content recommendations (playtime + YouTube demand)

**search/** — Search tools
- `search_tools.py` — Web search, news search, wiki lookup, reddit search, weather, fetch_url

**productivity/** — Productivity tools
- `calendar.py` — Google Calendar tools (today schedule, upcoming events, availability)
- `goals.py` — Goals, plans, tasks, commitments
- `personal.py` — Personal tasks (reminders, to-dos)
- `sync.py` — Google Tasks sync

**communication/** — Communication tools
- `gmail.py` — Gmail tools (dual account: personal + RFD IT Services)

**meta/** — Meta tools
- `meta.py` — think() scratchpad

**registry.py** — TOOL_REGISTRY (single source of truth for all 46 tools)

### API Layer (`api/`)

**google/** — Google APIs
- `youtube_api.py` — YouTube Analytics + Data API
- `gmail_api.py` — Gmail API (dual account)
- `calendar_api.py` — Google Calendar API
- `tasks_api.py` — Google Tasks API

**steam/** — Steam APIs
- `steam_api.py` — Steam Web API
- `steamspy_api.py` — SteamSpy API
- `itad_api.py` — IsThereAnyDeal API
- `catalog_api.py` — Steam catalog resolution

**web/** — Web APIs
- `ddg_api.py` — DuckDuckGo Search API
- `wikipedia_api.py` — Wikipedia API
- `reddit_api.py` — Reddit API
- `fetch_api.py` — Browser tool (requests + BeautifulSoup)

**weather/** — Weather API
- `weather_api.py` — Open-Meteo Weather API

**_handler.py** — BaseAPIHandler, BaseTool base classes

## 3. What the Tool Layer Does and Does NOT Do

### Responsibilities
- Business logic and domain-specific processing
- Scoring, ranking, and verdict generation
- Fuzzy matching and search logic
- Data transformation for tool output
- Combining data from multiple API calls
- Result shaping via BaseTool pattern (success(), error(), stale_notice())
- Tool registration in TOOL_REGISTRY

### What It Does NOT Do
- Direct HTTP requests to external APIs (delegated to API layer)
- API authentication (delegated to API layer)
- Raw response parsing (delegated to API layer)
- Cache management (delegated to CacheManager via BaseAPIHandler)
- Rate limit tracking (delegated to RateLimitManager via BaseAPIHandler)

## 4. What the API Layer Does and Does NOT Do

### Responsibilities
- HTTP communication with external APIs
- Authentication and credential management
- Request/response parsing and normalization
- API-specific error handling and retry logic
- Rate limit awareness via RateLimitManager
- Cache coordination via CacheManager
- 429 detection and retry_after extraction

### What It Does NOT Do
- Tool-specific business logic (delegated to tool layer)
- Scoring, ranking, or verdict generation (delegated to tool layer)
- Fuzzy matching or search algorithms (delegated to tool layer)
- Data transformation for tool output (delegated to tool layer)
- Direct cache operations (delegated to CacheManager)
- Direct rate limit operations (delegated to RateLimitManager)

## 5. BaseAPIHandler Pattern

### Purpose
Enforce consistent cache + rate limit behavior across all API clients. Subclasses set CACHE_PREFIX and call self.call() instead of cache directly.

### Class Definition (`api/_handler.py`)
```python
class BaseAPIHandler:
    CACHE_PREFIX: str = ""  # Must be set by subclass

    def _get_client(self):
        """Override to return authenticated client."""
        raise NotImplementedError

    def cache_key(self, suffix: str) -> str:
        """Namespaced cache key for this handler."""
        if not self.CACHE_PREFIX:
            raise NotImplementedError(
                f"{self.__class__.__name__} must set CACHE_PREFIX"
            )
        return f"{self.CACHE_PREFIX}_{suffix}"

    def call(self, suffix: str, params_hash: str, live_fn: Callable, stale_ok: bool = True) -> dict:
        """
        All API calls go through here.
        Delegates to CacheManager and RateLimitManager.
        """
        # Step 1 — fresh cache hit
        cached = cache.get(key, params_hash)
        if cached is not None:
            return cached

        # Step 2 — rate limit check
        if not rate_limits.can_call(self.CACHE_PREFIX):
            wait = rate_limits.time_until_available(self.CACHE_PREFIX)
            stale = cache.get_or_stale(key, params_hash)
            if stale is not None:
                return stale
            return {"error": f"{self.CACHE_PREFIX} rate limited", "_rate_limited": True, "_retry_after": wait}

        # Step 3 — live call
        try:
            result = live_fn()
            rate_limits.record_call(self.CACHE_PREFIX)
            cache.set(key, params_hash, result)
            return result
        except Exception as e:
            # Detect 429 and extract retry_after
            if "429" in str(e):
                rate_limits.record_limit(self.CACHE_PREFIX, retry_after)
            if stale_ok:
                stale = cache.get_or_stale(key, params_hash)
                if stale is not None:
                    return stale
            return {"error": str(e), "_live_failed": True}

    def hash(self, *args, **kwargs) -> str:
        """Convenience — delegates to cache.hash()."""
        return cache.hash(*args, **kwargs)
```

### Subclass Example
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

### The call() Flow
1. **Fresh cache hit** — return immediately from CacheManager
2. **Rate limit check** — RateLimitManager.can_call()
   - If rate limited: return stale data if available, else error with retry_after
3. **Live call** — execute live_fn()
   - On success: record_call(), cache.set(), return result
   - On 429: record_limit() with retry_after, fall through to stale fallback
   - On other error: fall through to stale fallback if stale_ok=True
4. **Stale fallback** — cache.get_or_stale() if stale_ok=True

### stale_ok=True vs stale_ok=False
- **stale_ok=True** (default): Return stale data on API failure. Used for most tools where some data is better than no data (weather, channel stats, game metrics).
- **stale_ok=False**: Never return stale data. Used for time-sensitive calls where freshness is critical (calendar get_events_soon, real-time queries).

### Write Operations Bypass Cache
Google Tasks push/complete/delete operations bypass cache entirely:
- No cache key generated
- No cache.set() call
- Direct API call only
- Ensures write operations always execute live

## 6. BaseTool Pattern

### Purpose
Enforce consistent return shape across all tool functions. Provides success() and error() helpers.

### Class Definition (`api/_handler.py`)
```python
class BaseTool:
    def success(self, data: dict, stale_result: dict = None) -> dict:
        """Return a successful result with optional stale notice."""
        result = {"ok": True, **data}
        if stale_result is not None:
            notice = cache.stale_notice(stale_result)
            if notice:
                result["_stale_notice"] = notice
        return result

    def error(self, message: str, code: int = None) -> dict:
        """Return an error result."""
        result = {"ok": False, "error": message}
        if code is not None:
            result["code"] = code
        return result

    def stale_notice(self, result: dict) -> str | None:
        """Extract stale notice from a result dict."""
        return cache.stale_notice(result)
```

### Return Shape Contract
```python
# Success
{
    "ok": True,
    "_stale_notice": None,  # or string if stale
    "temp_f": 83.6,        # tool-specific data
    ...
}

# Error
{
    "ok": False,
    "error": "Service unavailable",
    "code": 500,           # optional error code
    "_stale_notice": None
}
```

### Internal Key Stripping
BaseTool.success() strips internal keys from returned data:
- `_stale`, `_cached_at` removed before returning to agent
- Only `_stale_notice` surfaced to user
- Keeps agent response clean

## 7. Tool Categories

### content/ — YouTube Content Tools

**channel.py**
- `get_channel_summary()` — Channel metrics (views, watch time, subscribers)
- `get_daily_views()` — Daily view trends over time
- `get_audience_demographics()` — Age and gender breakdown
- `get_device_breakdown()` — Mobile vs desktop vs TV vs tablet
- `get_geographic_breakdown()` — Top 25 countries by views

**videos.py**
- `get_top_videos()` — Top videos by views
- `get_video_analytics()` — Per-video analytics (views, retention, avg view duration)
- `get_retention_curve()` — Retention curve showing where viewers drop off

**discovery.py**
- `get_traffic_sources()` — Top search terms driving traffic

### games/ — Game Tools

**metrics.py**
- `get_game_metrics()` — Game performance (players, owners, content gap, verdict)
- `get_installed_games()` — Installed games on this machine
- `get_sale_info()` — Current prices and historical lows

**recommendations.py**
- `get_content_recommendations()` — Ranked content recommendations (playtime + YouTube demand)

### search/ — Search Tools

**search_tools.py**
- `web_search()` — DuckDuckGo web search
- `news_search()` — DuckDuckGo news search
- `wiki_lookup()` — Wikipedia topic lookup
- `reddit_search()` — Reddit search (with optional subreddit filter)
- `get_weather()` — Open-Meteo weather (South Florida)
- `fetch_url()` — Browser tool (fetch full page content via requests + BeautifulSoup)

### productivity/ — Productivity Tools

**calendar.py**
- `get_today_schedule()` — Today's calendar events
- `get_upcoming_events()` — Upcoming events (default 7 days)
- `check_availability()` — Check if busy on a specific date

**goals.py**
- `save_commitment()` — Save a commitment
- `get_goals_list()` — List all goals
- `get_goal_detail()` — Get goal details
- `get_current_plan()` — Get current weekly plan
- `get_tasks_today()` — Get tasks due today
- `get_upcoming_tasks()` — Get upcoming tasks
- `update_task()` — Update task status
- `add_new_task()` — Add new task to goal
- `suggest_goal_progress()` — Suggest goal progress (agent never updates autonomously)

**personal.py**
- `add_personal_task()` — Add personal task (reminder/to-do)
- `list_personal_tasks()` — List personal tasks (filter: all/today/overdue)
- `complete_personal_task()` — Complete personal task
- `snooze_personal_task()` — Snooze personal task
- `delete_personal_task()` — Delete personal task

**sync.py**
- `run_sync()` — Run Google Tasks sync
- `pull_from_google()` — Pull tasks from Google
- `push_new_tasks()` — Push new tasks to Google

### communication/ — Communication Tools

**gmail.py**
- `get_inbox_summary()` — Get inbox summary (personal only)
- `get_all_inbox_summary()` — Get inbox summary (personal + RFD IT Services)
- `search_email()` — Search emails by query
- `check_sender()` — Check if specific sender emailed (single account)
- `check_sender_all()` — Check if specific sender emailed (both accounts)
- `read_email()` — Read specific email content

### meta/ — Meta Tools

**meta.py**
- `think()` — Scratchpad for agent reasoning (not BaseTool — no network, no cache)

## 8. API Sources

### google/ — Google APIs

**youtube_api.py**
- YouTube Analytics API (channel data, video data, daily views, demographics, device breakdown, geographic breakdown, traffic sources)
- YouTube Data API (search videos, video statistics)
- Uses OAuth token from config/youtube_token.json

**gmail_api.py**
- Gmail API (inbox summary, search emails, check sender, read email)
- Dual account support: personal (cheater2478@gmail.com) + RFD IT Services
- Uses OAuth tokens from config/youtube_token.json and config/rfd_token.json

**calendar_api.py**
- Google Calendar API (get events, get events today, get upcoming events)
- Uses OAuth token from config/youtube_token.json

**tasks_api.py**
- Google Tasks API (get default tasklist, pull tasks, push task, delete task)
- Uses OAuth token from config/youtube_token.json
- Write operations bypass cache

### steam/ — Steam APIs

**steam_api.py**
- Steam Web API (get owned games, get app list, get app details)
- Uses STEAM_API_KEY from environment

**steamspy_api.py**
- SteamSpy API (get app details, get owners, get players)
- No API key required

**itad_api.py**
- IsThereAnyDeal API (search games, get prices, get historical low)
- Uses ITAD_API_KEY from environment

**catalog_api.py**
- Steam catalog resolution (resolve game name to AppID)
- Uses Steam catalog API

### web/ — Web APIs

**ddg_api.py**
- DuckDuckGo Search API (web search, news search)
- No API key required

**wikipedia_api.py**
- Wikipedia API (get summary)
- No API key required

**reddit_api.py**
- Reddit API (search)
- No API key required

**fetch_api.py**
- Browser tool (fetch URL content via requests + BeautifulSoup)
- No API key required
- Removes noise elements (script, style, nav, header, footer, aside, form)

### weather/ — Weather API

**weather_api.py**
- Open-Meteo Weather API (get current weather)
- No API key required
- South Florida location hardcoded

## 9. Tool Registry Format

### Registry Structure
```python
TOOL_REGISTRY = {
    "tool_name": {
        "fn": function_reference,
        "definition": {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "Human-readable description",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param_name": {
                            "type": "string|integer|array|boolean",
                            "description": "Parameter description",
                            "default": optional_default
                        }
                    },
                    "required": ["param_name"]
                }
            }
        }
    }
}
```

### Registry Principles
- Single source of truth for tool discovery
- OpenAI-compatible function calling schema
- Function references (not strings) for type safety
- Centralized in tools/registry.py
- No logic, only imports and definitions
- Consumed by agent for tool calling
- Consumed by MCP server (Phase 15) for Claude Desktop integration

### Tool Count
- 46 tools total across 6 categories
- content: 9 tools
- games: 4 tools
- search: 6 tools
- productivity: 16 tools
- communication: 6 tools
- meta: 1 tool
- memory: 4 tools (defined in bot/memory.py, imported in registry)

### Agent Integration
```python
# Discovery
tools_definitions = [t["definition"] for t in TOOL_REGISTRY.values()]

# Execution
result = TOOL_REGISTRY["tool_name"]["fn"](**params)
```

### MCP Integration (Phase 15)
```python
# MCP server reads TOOL_REGISTRY directly
for tool_name, tool_data in TOOL_REGISTRY.items():
    mcp_tool = convert_to_mcp_schema(tool_data["definition"])
    register_mcp_tool(tool_name, mcp_tool)
```

## 10. Return Shape Contract

### Success Shape
```python
{
    "ok": True,
    "_stale_notice": None,  # or string if stale
    "temp_f": 83.6,        # tool-specific data
    ...
}
```

### Error Shape
```python
{
    "ok": False,
    "error": "Service unavailable",
    "code": 500,           # optional error code
    "_stale_notice": None
}
```

### Stale Notice Format
- `None` for fresh data
- String for stale data: "⚠️ Data from 4h ago (2026-05-30 09:15)"
- Agent surfaces stale_notice to user
- Tool functions use BaseTool.success() to extract stale_notice from API result

### Internal Keys (Stripped)
- `_stale` — removed by BaseTool.success()
- `_cached_at` — removed by BaseTool.success()
- `_rate_limited` — removed by BaseTool.success()
- `_retry_after` — removed by BaseTool.success()
- `_live_failed` — removed by BaseTool.success()
- Only `_stale_notice` surfaced to user

## 11. Adding a New Tool

### Step 1: Implement Tool Function
```python
# tools/category/new_tool.py
from api.source.source_api import api_function
from api._handler import BaseTool
from infra.cache import cache

class NewTool(BaseTool):
    def my_tool(self, param: str) -> dict:
        # Call API via BaseAPIHandler
        handler = SourceAPIHandler()
        result = handler.call("endpoint", handler.hash(param), lambda: api_function(param))
        
        if "error" in result:
            return self.error(result["error"])
        
        # Process data
        processed = {"processed_data": result["raw"]}
        return self.success(processed, stale_result=result)
```

### Step 2: Register in TOOL_REGISTRY
```python
# tools/registry.py
from .category.new_tool import NewTool

new_tool_instance = NewTool()

TOOL_REGISTRY = {
    "my_tool": {
        "fn": new_tool_instance.my_tool,
        "definition": {
            "type": "function",
            "function": {
                "name": "my_tool",
                "description": "Tool description",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param": {
                            "type": "string",
                            "description": "Parameter description"
                        }
                    },
                    "required": ["param"]
                }
            }
        }
    }
}
```

### Step 3: Test Tool
```python
# test_new_tool.py
from tools.category.new_tool import NewTool

tool = NewTool()
result = tool.my_tool("test_value")
assert result["ok"] == True
```

### Step 4: Update Documentation
- Add tool to this SDD in appropriate category section
- Update ADR-003 if new TTL needed
- Add examples to relevant docs

## 12. Adding a New API Integration

### Step 1: Create API Handler
```python
# api/source/new_api.py
from api._handler import BaseAPIHandler

class NewAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "new_api"

    def _get_client(self):
        # Load credentials
        return authenticated_client

    def get_data(self, param: str) -> dict:
        def _live():
            # HTTP call
            return {"raw": response}
        return self.call("endpoint", self.hash(param), _live)
```

### Step 2: Add Credentials to .env
```bash
# .env
NEW_API_KEY=your_api_key_here
```

### Step 3: Update .env.example
```bash
# config/.env.example
NEW_API_KEY=
```

### Step 4: Test API Handler
```python
# test_new_api.py
from api.source.new_api import NewAPIHandler

handler = NewAPIHandler()
result = handler.get_data("test_value")
print(result)
```

### Step 5: Document API Contract
Add function documentation to ADR-001 or API-specific doc.

## 13. Testing Strategy

### API Layer Tests
- Mock HTTP requests
- Test error handling
- Test retry logic
- Test authentication
- Test 429 detection and retry_after extraction
- Test rate limit coordination
- Test cache coordination

### Tool Layer Tests
- Mock API layer
- Test business logic
- Test BaseTool return shapes
- Test error propagation
- Test stale_notice extraction
- Test internal key stripping

### Integration Tests
- Test full tool execution
- Test cache hit/miss
- Test stale fallback
- Test rate limit behavior
- Test error scenarios
- Test agent integration
- Test MCP server integration (Phase 15)

## 14. Related ADRs

- [ADR-001: API/Tool Separation Pattern](../adr/ADR-001.md) — Separation between API clients and tool logic
- [ADR-002: Tool Registry Pattern](../adr/ADR-002.md) — Centralized tool discovery via TOOL_REGISTRY
- [ADR-003: Caching Strategy](../adr/ADR-003.md) — SQLite-based caching with per-tool TTL
- [ADR-011: Tool Architecture](../adr/ADR-011.md) — Tools as plug-ins with TOOL_REGISTRY pattern
- [ADR-018: Offline-First Cache Strategy](../adr/ADR-018.md) — Staleness budget per API
- [ADR-019: Staleness Budget per API](../adr/ADR-019.md) — Acceptable stale age per tool
- [ADR-020: Preload on Startup Pattern](../adr/ADR-020.md) — Warm cache on startup
- [ADR-023: DBManager](../adr/ADR-023.md) — Single owner of database access with retry logic
- [ADR-024: fetch_url Browser Tool](../adr/ADR-024.md) — Browser tool for reading full web page content
- [ADR-025: think Scratchpad Tool](../adr/ADR-025.md) — Scratchpad tool for context continuity
- [ADR-026: RateLimitManager Layer](../adr/ADR-026.md) — API rate limit tracking and quota awareness
- [ADR-027: PollingManager Layer](../adr/ADR-027.md) — Single owner of polling behavior
- [ADR-033: MCP Compatibility](../adr/ADR-033.md) — Expose 46 tools to Claude via MCP server (Phase 15)
