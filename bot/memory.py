"""Layer 4 — Memory.

Wraps db.py with agent-facing tool functions and their OpenRouter
tool definitions. Only the Agent layer calls these.
Pure memory logic: no Telegram, OpenRouter, routing, or report code.
"""

from infra.db import save_memory, update_memory, retire_memory, get_memories

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
