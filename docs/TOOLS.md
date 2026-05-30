# Tools Guide

This guide explains how to add new tools to PrivyBot. Tools are functions the AI can call to perform actions beyond text generation — saving memories, fetching data, executing code, etc.

## Tool Architecture

Tools follow the OpenAI function calling format:

1. **Tool Definition** — JSON schema describing the tool (name, description, parameters)
2. **Tool Implementation** — Python function that executes the tool
3. **Agent Integration** — Agent calls the tool when OpenRouter returns a tool_call
4. **Result Return** — Tool result is fed back to the model for completion

## Tool Definition Format

Tools are defined in `memory.py` in the `TOOL_DEFINITIONS` list:

```python
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save a fact about Robert to long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Short identifier for the memory (e.g., 'daughter')",
                    },
                    "content": {
                        "type": "string",
                        "description": "The fact to remember",
                    },
                    "layer": {
                        "type": "string",
                        "description": "Category: personal, business, technical, project, content",
                        "enum": ["personal", "business", "technical", "project", "content"],
                    },
                },
                "required": ["key", "content", "layer"],
            },
        },
    },
    # ... more tools
]
```

**Key fields:**
- `name`: Function name (must match implementation)
- `description`: What the tool does (the model reads this to decide when to call it)
- `parameters`: JSON Schema for input validation
- `required`: List of required parameter names

## Tool Implementation

Tool implementations are also in `memory.py`:

```python
def tool_save_memory(key: str, content: str, layer: str) -> dict:
    """Save a memory to the database."""
    from db import save_memory
    save_memory(key, content, layer)
    return {"status": "saved", "key": key}
```

**Tool return shape:**
```python
{
    "status": "success|error",
    "key": "...",  # optional: identifier
    "result": "...",  # optional: data payload
    "error": "...",  # optional: error message
}
```

The return value is fed back to the model as a tool result message. The model uses this to continue the conversation.

## Agent Integration

The agent (`agent.py`) handles tool execution in the `_execute()` function:

```python
async def _execute(thread_id: str, name: str, args: dict) -> dict:
    if name == "save_memory":
        r = tool_save_memory(args["key"], args["content"], args["layer"])
        await report("memory_saved", key=args["key"], layer=args["layer"], content=args["content"])
        return r
    # ... more tools
```

When you add a new tool, you must:
1. Add the definition to `TOOL_DEFINITIONS` in `memory.py`
2. Implement the function in `memory.py`
3. Add a handler in `_execute()` in `agent.py`
4. (Optional) Add a report event in `report.py` for logging

## Example: Adding a YouTube Stats Tool

Let's add a tool that fetches YouTube channel statistics.

### Step 1: Add Tool Definition

In `memory.py`, add to `TOOL_DEFINITIONS`:

```python
{
    "type": "function",
    "function": {
        "name": "youtube_stats",
        "description": "Fetch YouTube channel statistics (subscribers, views, video count).",
        "parameters": {
            "type": "object",
            "properties": {
                "channel_id": {
                    "type": "string",
                    "description": "YouTube channel ID (e.g., 'UCxxxxxxxxxxxxxxxxxxxxxx')",
                },
            },
            "required": ["channel_id"],
        },
    },
},
```

### Step 2: Implement Tool Function

In `memory.py`, add the implementation:

```python
def tool_youtube_stats(channel_id: str) -> dict:
    """Fetch YouTube channel statistics."""
    import httpx

    try:
        # YouTube Data API v3
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return {"status": "error", "error": "YOUTUBE_API_KEY not set"}

        url = f"https://www.googleapis.com/youtube/v3/channels"
        params = {
            "part": "statistics",
            "id": channel_id,
            "key": api_key,
        }

        resp = httpx.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("items"):
            return {"status": "error", "error": "Channel not found"}

        stats = data["items"][0]["statistics"]
        return {
            "status": "success",
            "result": {
                "subscribers": stats["subscriberCount"],
                "views": stats["viewCount"],
                "videos": stats["videoCount"],
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

### Step 3: Add Agent Handler

In `agent.py`, add to `_execute()`:

```python
async def _execute(thread_id: str, name: str, args: dict) -> dict:
    # ... existing tools
    if name == "youtube_stats":
        r = tool_youtube_stats(args["channel_id"])
        await report("youtube_stats_fetched", channel_id=args["channel_id"])
        return r
```

### Step 4: Add Report Event (Optional)

In `report.py`, add to the event mapping:

```python
EVENTS = {
    # ... existing events
    "youtube_stats_fetched": "📊 YouTube stats fetched for {channel_id}",
}
```

### Step 5: Add API Key to .env

```
YOUTUBE_API_KEY=AIzaSy...
```

### Step 6: Test

Send a message to the bot:
```
"Get the stats for my YouTube channel UCxxxxxxxxxxxxxxxxxxxxxx"
```

The model should call `youtube_stats` and return the statistics.

## Tool Best Practices

### 1. Descriptive Names and Descriptions

The model reads the description to decide when to call the tool. Be specific:

```python
# Good
{
    "name": "save_memory",
    "description": "Save a fact about Robert to long-term memory. Use for: projects, decisions, preferences, goals, people, technical choices. Never save casual conversation.",
}

# Bad
{
    "name": "save",
    "description": "Save something",
}
```

### 2. Validate Inputs

Tool functions should validate inputs and return errors:

```python
def tool_save_memory(key: str, content: str, layer: str) -> dict:
    if not key or not key.strip():
        return {"status": "error", "error": "key cannot be empty"}
    if layer not in ["personal", "business", "technical", "project", "content"]:
        return {"status": "error", "error": f"invalid layer: {layer}"}
    # ... proceed
```

### 3. Handle External API Failures

External APIs can fail. Handle gracefully:

```python
def tool_youtube_stats(channel_id: str) -> dict:
    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        # ... process
    except httpx.TimeoutException:
        return {"status": "error", "error": "YouTube API timeout"}
    except httpx.HTTPStatusError as e:
        return {"status": "error", "error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

### 4. Report Events

Log tool calls for debugging and monitoring:

```python
async def _execute(thread_id: str, name: str, args: dict) -> dict:
    if name == "youtube_stats":
        r = tool_youtube_stats(args["channel_id"])
        await report("youtube_stats_fetched", channel_id=args["channel_id"])
        return r
```

### 5. Keep Tools Focused

Each tool should do one thing well. Don't combine unrelated operations:

```python
# Bad: combines fetching and saving
def tool_fetch_and_save_youtube_stats(channel_id: str) -> dict:
    stats = fetch_stats(channel_id)
    save_memory("youtube_stats", json.dumps(stats), "content")
    return stats

# Good: separate tools
def tool_youtube_stats(channel_id: str) -> dict:
    return fetch_stats(channel_id)

def tool_save_memory(key: str, content: str, layer: str) -> dict:
    save_memory(key, content, layer)
    return {"status": "saved"}
```

The model can chain tools: call `youtube_stats`, then call `save_memory` with the result.

## Tool Return Shape

Standard return format:

```python
{
    "status": "success" | "error",
    "key": "...",  # optional: identifier
    "result": {...},  # optional: data payload
    "error": "...",  # optional: error message (when status is error)
}
```

**Success example:**
```python
{
    "status": "success",
    "result": {
        "subscribers": "1000",
        "views": "50000",
        "videos": "50",
    },
}
```

**Error example:**
```python
{
    "status": "error",
    "error": "YouTube API timeout",
}
```

## Advanced: Tool Chaining

The model can chain tools automatically. Example conversation:

```
User: "Get my YouTube stats and save them to memory"
Model: [calls youtube_stats]
Tool: {"status": "success", "result": {"subscribers": "1000", ...}}
Model: [calls save_memory with key="youtube_stats", content="..."]
Tool: {"status": "saved"}
Model: "Saved your YouTube stats: 1000 subscribers, 50000 views, 50 videos."
```

No special code needed — the model handles chaining based on tool results.

## Testing Tools

Test tools manually before deploying:

```python
# test_tool.py
from memory import tool_youtube_stats

result = tool_youtube_stats("UCxxxxxxxxxxxxxxxxxxxxxx")
print(result)
```

Run: `uv run python test_tool.py`

## Current Tools

PrivyBot includes these built-in tools:

- `save_memory` — Save a fact to long-term memory
- `update_memory` — Update an existing memory
- `retire_memory` — Deactivate a memory
- `get_memories` — Retrieve memories by query
- `name_thread` — Name the current thread

See `memory.py` for their definitions and implementations.

## Adding Tools That Modify State

If a tool modifies state (database, files, external systems), consider:

1. **Idempotency** — Can the tool be called multiple times safely?
2. **Rollback** — Can changes be undone if needed?
3. **Logging** — Log all state changes for audit
4. **Permissions** — Ensure the tool has required permissions

Example: A tool that creates a file should check if it exists first:

```python
def tool_create_file(path: str, content: str) -> dict:
    if os.path.exists(path):
        return {"status": "error", "error": "File already exists"}
    with open(path, "w") as f:
        f.write(content)
    return {"status": "success", "path": path}
```

## Security Considerations

- Tools can execute arbitrary code — validate all inputs
- Tools with external APIs should use API keys from environment variables
- Never hardcode secrets in tool implementations
- Consider rate limiting for external API calls
- Log all tool calls for security auditing

## Summary

To add a new tool:

1. Define the tool schema in `memory.py` (`TOOL_DEFINITIONS`)
2. Implement the function in `memory.py`
3. Add a handler in `agent.py` (`_execute()`)
4. (Optional) Add a report event in `report.py`
5. Add required environment variables to `.env`
6. Test the tool manually
7. Deploy and test end-to-end

This is how PrivyBot grows — tools are the extension points for new capabilities.
