"""Layer 4 — Memory.

Wraps db.py with agent-facing tool functions and their OpenRouter
tool definitions. Only the Agent layer calls these.
Pure memory logic: no Telegram, OpenRouter, routing, or report code.
"""

from core.db import save_memory, update_memory, retire_memory, get_memories

VALID_LAYERS = {"technical", "project", "personal", "business", "content"}


def tool_save_memory(key: str, content: str, layer: str) -> dict:
    if layer not in VALID_LAYERS:
        return {"status": "error", "reason": f"invalid layer '{layer}'"}
    save_memory(key, content, layer)
    return {"status": "saved", "key": key, "layer": layer, "content": content}


def tool_update_memory(key: str, content: str, reason: str) -> dict:
    update_memory(key, content)
    return {"status": "updated", "key": key, "reason": reason, "content": content}


def tool_retire_memory(key: str, reason: str) -> dict:
    retire_memory(key)
    return {"status": "retired", "key": key, "reason": reason}


def tool_get_memories(query: str) -> dict:
    results = get_memories(query, limit=5)
    if not results:
        return {"status": "empty", "count": 0}
    return {"status": "found", "count": len(results), "memories": results}


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save a durable fact about Robert. Use for projects, "
                           "decisions, preferences, goals, people, technical choices. "
                           "Never save casual conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short unique slug"},
                    "content": {"type": "string", "description": "The fact to remember"},
                    "layer": {
                        "type": "string",
                        "enum": ["technical", "project", "personal", "business", "content"],
                    },
                },
                "required": ["key", "content", "layer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_memory",
            "description": "Update an existing memory when information changes. "
                           "Call immediately when the user corrects you.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "content": {"type": "string", "description": "The new content"},
                    "reason": {"type": "string", "description": "What changed and why"},
                },
                "required": ["key", "content", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retire_memory",
            "description": "Deactivate a memory that is no longer true or relevant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "reason": {"type": "string", "description": "Why it is retired"},
                },
                "required": ["key", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_memories",
            "description": "Search active memories before responding on a new topic. "
                           "Returns up to 5 matches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
]
