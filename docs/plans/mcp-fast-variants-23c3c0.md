# MCP Fast Variants with Transparent Fallback

Add fast variants for slow MCP tools to prevent timeouts while keeping all 70 tools visible.

## Problem
- `get_memories` triggers Chroma + Ollama embedding → 4-minute timeout
- Heavy repo tools (read_current_state, find_opportunities) timeout
- No timeout wrapper → tools hang instead of failing fast

## Solution
Transparent fallback system: fast-first routing with timeout wrapper. All 70 tools remain visible, but slow tools try fast path first (~50ms) and escalate to full only if needed.

## Design

### Fast Variants (MCP_FAST_VARIANTS)
- `get_memories` → `memory_manager.search_simple()` (SQLite LIKE, <50ms)
- `read_current_state` → `get_state_summary()` (DB + git log, no file reads)
- `find_opportunities` → `get_quick_opportunities()` (cached result from DB)

### Fast-First Routing
```python
@server.call_tool()
async def call_tool(name, arguments):
    fast_fn = MCP_FAST_VARIANTS.get(name)
    
    if fast_fn:
        # Try fast path first (~100ms)
        result = fast_fn(**arguments)
        if result.get("ok"):
            return [TextContent(..., text=json.dumps(result))]
    
    # Fast failed or no fast variant → try full tool with timeout
    try:
        result = await asyncio.wait_for(run_tool(name, arguments), timeout=30.0)
    except asyncio.TimeoutError:
        return [TextContent(..., text=json.dumps({
            "ok": False, "error": f"{name} timed out — try a more specific query"
        }))]
```

## Files
- `infra/mcp/config.py` — add MCP_FAST_VARIANTS dict
- `infra/memory_manager.py` — add search_simple() method
- `infra/mcp/fast.py` — new file with get_state_summary(), get_quick_opportunities()
- `infra/mcp/server.py` — fast-first routing + timeout wrapper

## Stop Rule
- infra/mcp/config.py — MCP_FAST_VARIANTS only
- infra/memory_manager.py — search_simple() only
- infra/mcp/fast.py — new file only
- infra/mcp/server.py — call_tool handler only
- No changes to TOOL_REGISTRY, tool schemas, or MCP_EXPOSED_TOOLS

## Success
- 330/330 tests pass
- get_memories returns in <100ms via MCP
- Heavy tools fail fast with clean error instead of 4-minute hang
- All 70 tools remain visible in tool picker
