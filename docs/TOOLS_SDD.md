# Tools Software Design Document

## 1. Architecture Overview

PrivyBot's tools system is organized into two distinct layers with clear separation of concerns:

```
tools/
  api/                    ← API Layer
    youtube_api.py        ← YouTube Analytics + Data API
    steam_api.py          ← Steam Web API
    steamspy_api.py       ← SteamSpy API
    itad_api.py           ← IsThereAnyDeal API
  
  tools/                  ← Tool Layer
    channel_tools.py      ← Channel metrics tools
    game_tools.py         ← Game metrics tools
    recommendation_tools.py  ← Content recommendation tools
  
  __init__.py             ← Tool Registry (TOOL_REGISTRY)
```

**Key Principles:**
- API Layer: Knows how to talk to external services
- Tool Layer: Knows what to do with the data
- Registry: Single source of truth for tool discovery

**Data Flow:**
```
Agent → Tool Registry → Tool Function → API Client → External Service
         (definition)    (business logic)   (raw API call)
```

## 2. API Layer

### Responsibilities
- HTTP communication with external APIs
- Authentication and credential management
- Request/response parsing and normalization
- API-specific error handling and retry logic
- Rate limit awareness

### What It Does NOT Do
- Tool-specific business logic
- Scoring, ranking, or verdict generation
- Fuzzy matching or search algorithms
- Data transformation for tool output
- Caching (handled at tool layer per ADR-003)

### Function Contract
```python
def api_function(params: dict) -> dict:
    """
    Raw API call.
    
    Args:
        params: API-specific parameters
        
    Returns:
        dict: Raw API response or error dict
        
    Contract:
        - Never raises exceptions
        - Returns {"error": str} on failure
        - Returns {"raw": response} on success
        - Handles auth internally
        - Handles retries internally
    """
```

### File Structure

**tools/api/youtube_api.py**
```python
# YouTube Analytics API
def get_channel_data(days: int) -> dict
def get_top_videos_data(days: int, limit: int) -> dict
def get_video_data(video_id: str, days: int) -> dict

# YouTube Data API
def search_videos(query: str, days: int) -> dict
def get_video_statistics(video_ids: list[str]) -> dict

# Internal
def _get_credentials() -> Credentials
def _build_analytics_client() -> Resource
def _build_data_client() -> Resource
```

**tools/api/steam_api.py**
```python
# Steam Web API
def get_owned_games() -> dict
def get_app_list() -> dict
def get_app_details(appid: int) -> dict

# Internal
def _get_steam_api() -> str
```

**tools/api/steamspy_api.py**
```python
# SteamSpy API
def get_app_details(appid: int) -> dict
def get_owners(appid: int) -> dict
def get_players(appid: int) -> dict

# Internal
def _get_steamspy_api() -> str
```

**tools/api/itad_api.py**
```python
# IsThereAnyDeal API
def search_games(title: str) -> dict
def get_prices(game_ids: list[str]) -> dict
def get_historical_low(game_id: str) -> dict

# Internal
def _get_itad_api() -> str
def _get_api_key() -> str
```

### Error Handling
```python
# Standard error response
{
    "error": "Human-readable error message",
    "error_type": "api_error|auth_error|rate_limit|timeout",
    "retryable": True|False
}

# Success response
{
    "raw": <API response data>,
    "cached": False  # Future: indicate if API returned cached data
}
```

## 3. Tool Layer

### Responsibilities
- Business logic and domain-specific processing
- Scoring, ranking, and verdict generation
- Fuzzy matching and search logic
- Data transformation for tool output
- Combining data from multiple API calls
- Caching (per ADR-003)

### What It Does NOT Do
- Direct HTTP requests to external APIs
- API authentication
- Raw response parsing (delegated to API layer)

### Function Contract
```python
def tool_function(params: dict) -> dict:
    """
    Tool with business logic.
    
    Args:
        params: Tool parameters from agent
        
    Returns:
        dict: Shaped tool response or error dict
        
    Contract:
        - Imports from tools.api/ only
        - Never raises exceptions
        - Returns {"error": str} on failure
        - Applies caching per ADR-003
        - Returns shaped response for agent
    """
```

### File Structure

**tools/tools/channel_tools.py**
```python
from tools.api.youtube_api import (
    get_channel_data,
    get_top_videos_data,
    get_video_data
)
from core.db import cache_tool_result, get_cached_tool_result

def get_channel_summary(days: int = 7) -> dict
def get_top_videos(days: int = 7, limit: int = 10) -> dict
def get_video_analytics(video_id: str, days: int = 28) -> dict

# Internal
def _hash_params(params: dict) -> str
```

**tools/tools/game_tools.py**
```python
from tools.api.steam_api import get_owned_games, get_app_list
from tools.api.steamspy_api import get_app_details
from tools.api.itad_api import search_games, get_prices
from core.db import cache_tool_result, get_cached_tool_result

def get_game_metrics(game_name: str) -> dict
def get_installed_games() -> dict
def get_sale_info(game_names: list[str]) -> dict

# Internal
def resolve_appid(game_name: str) -> dict | None
def _hash_params(params: dict) -> str
```

**tools/tools/recommendation_tools.py**
```python
from tools.api.steam_api import get_owned_games
from tools.api.steamspy_api import get_app_details
from tools.api.youtube_api import search_videos, get_video_statistics
from core.db import cache_tool_result, get_cached_tool_result

def get_content_recommendations(limit: int = 5, min_playtime: float = 1.0) -> dict

# Internal
def score_game(game: dict, steam_data: dict, yt_data: dict) -> float
def _hash_params(params: dict) -> str
```

### Response Format
```python
# Standard tool response
{
    "data": <tool-specific data>,
    "_cached": True|False,  # Indicates if from cache
    "_fetched_at": "ISO 8601 timestamp",  # When data was fetched
    "_expires_at": "ISO 8601 timestamp"  # When cache expires
}

# Error response
{
    "error": "Human-readable error message",
    "error_type": "api_error|validation_error|not_found"
}
```

## 4. Adding a New API Integration

### Step 1: Create API Client
```python
# tools/api/new_api.py
import os
import requests

API_KEY = os.getenv("NEW_API_KEY")
API_BASE = "https://api.example.com"

def get_data(params: dict) -> dict:
    """Raw API call."""
    try:
        response = requests.get(
            f"{API_BASE}/endpoint",
            params=params,
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=10
        )
        response.raise_for_status()
        return {"raw": response.json()}
    except Exception as e:
        return {"error": str(e)}
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

### Step 4: Test API Client
```python
# test_new_api.py
from tools.api.new_api import get_data

result = get_data({"param": "value"})
print(result)
```

### Step 5: Document API Contract
Add function documentation to ADR-001 or API-specific doc.

## 5. Adding a New Tool

### Step 1: Implement Tool Function
```python
# tools/tools/new_tools.py
from tools.api.new_api import get_data
from core.db import cache_tool_result, get_cached_tool_result
import hashlib
import json

def _hash_params(params: dict) -> str:
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()

def new_tool(param: str) -> dict:
    """Tool description."""
    # Check cache
    params_hash = _hash_params({"param": param})
    cached = get_cached_tool_result("new_tool", params_hash)
    if cached:
        return cached
    
    # Fetch data
    api_response = get_data({"param": param})
    if "error" in api_response:
        return {"error": api_response["error"]}
    
    # Process data
    result = {
        "data": api_response["raw"],
        "processed": True
    }
    
    # Cache result
    cache_tool_result("new_tool", params_hash, result, ttl_hours=6)
    
    return result
```

### Step 2: Register in TOOL_REGISTRY
```python
# tools/__init__.py
from tools.tools.new_tools import new_tool

TOOL_REGISTRY = {
    "new_tool": {
        "fn": new_tool,
        "definition": {
            "type": "function",
            "function": {
                "name": "new_tool",
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
from tools.tools.new_tools import new_tool

result = new_tool("test_value")
print(result)
```

### Step 4: Update Documentation
- Add tool to TOOLS.md
- Update ADR-003 if new TTL needed
- Add examples to relevant docs

## 6. Caching Policy

### Cache Storage
- Table: `tool_cache` in SQLite (core/db.py)
- Key: `(tool_name, params_hash)`
- Value: JSON-encoded result
- Expiration: ISO 8601 timestamp

### TTL Values (per ADR-003)
- YouTube Analytics: 6 hours
- Steam/SteamSpy: 24 hours
- IsThereAnyDeal: 1 hour
- Content Recommendations: 12 hours
- Installed Games: 1 hour

### Cache Pattern
```python
def tool_function(params: dict) -> dict:
    # 1. Compute cache key
    params_hash = _hash_params(params)
    
    # 2. Check cache
    cached = get_cached_tool_result("tool_function", params_hash)
    if cached:
        return cached
    
    # 3. Fetch fresh data
    result = api_call(params)
    
    # 4. Cache result
    cache_tool_result("tool_function", params_hash, result, ttl_hours=TTL)
    
    return result
```

### Cache Invalidation
- Automatic: Expired entries ignored on read
- Manual: Delete by tool_name or params_hash
- Scheduled: Daily cleanup of expired entries

## 7. Error Handling Contract

### API Layer Errors
```python
{
    "error": "Human-readable message",
    "error_type": "api_error|auth_error|rate_limit|timeout",
    "retryable": True|False,
    "status_code": int  # HTTP status if applicable
}
```

### Tool Layer Errors
```python
{
    "error": "Human-readable message",
    "error_type": "api_error|validation_error|not_found|cache_error"
}
```

### Error Propagation
- API errors propagate to tool layer
- Tool layer adds context and returns to agent
- Agent presents error to user
- Never raise exceptions — always return error dict

### Validation Errors
```python
{
    "error": "Invalid parameter: days must be positive integer",
    "error_type": "validation_error",
    "invalid_params": ["days"]
}
```

## 8. Tool Registry Format

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
- Centralized in tools/__init__.py
- No logic, only imports and definitions

### Agent Integration
```python
# Discovery
tools_definitions = [t["definition"] for t in TOOL_REGISTRY.values()]

# Execution
result = TOOL_REGISTRY["tool_name"]["fn"](**params)
```

## 9. Migration Path

### Current State
- `tools/youtube.py` — mixed API + tool logic
- `tools/games.py` — mixed API + tool logic
- `tools/recommendations.py` — mixed API + tool logic
- `tools/__init__.py` — TOOL_REGISTRY with direct imports

### Target State
- `tools/api/` — pure API clients
- `tools/tools/` — pure tool logic
- `tools/__init__.py` — TOOL_REGISTRY only

### Migration Steps
1. Create `tools/api/` directory
2. Extract API calls from existing files
3. Create `tools/tools/` directory
4. Refactor tool functions to use API layer
5. Update `tools/__init__.py` imports
6. Test all tools before/after migration
7. Delete old files

### Zero Behavior Change
- All tool functions maintain same signatures
- All tool responses maintain same format
- All tool registrations maintain same names
- Agent integration unchanged

## 10. Testing Strategy

### API Layer Tests
- Mock HTTP requests
- Test error handling
- Test retry logic
- Test authentication

### Tool Layer Tests
- Mock API layer
- Test business logic
- Test caching
- Test error propagation

### Integration Tests
- Test full tool execution
- Test cache hit/miss
- Test error scenarios
- Test agent integration

## References
- [ADR-001: API/Tool Separation Pattern](adr/ADR-001.md)
- [ADR-002: Tool Registry Pattern](adr/ADR-002.md)
- [ADR-003: Caching Strategy](adr/ADR-003.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [TOOLS.md](TOOLS.md)
