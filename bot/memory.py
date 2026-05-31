"""Layer 4 — Memory.

Wraps memory_manager with agent-facing tool functions and their OpenRouter
tool definitions. Only the Agent layer calls these.
Pure memory logic: no Telegram, OpenRouter, routing, or report code.
"""

from infra.memory_manager import memory_manager

VALID_LAYERS = {"technical", "project", "personal", "business", "content"}


def tool_save_memory(key: str, content: str, layer: str) -> dict:
    if layer not in VALID_LAYERS:
        return {"status": "error", "reason": f"invalid layer '{layer}'"}
    memory_manager.save(key, content, layer)
    return {"status": "saved", "key": key, "layer": layer, "content": content}


def tool_update_memory(key: str, content: str, reason: str) -> dict:
    memory_manager.update(key, content)
    return {"status": "updated", "key": key, "reason": reason, "content": content}


def tool_retire_memory(key: str, reason: str) -> dict:
    memory_manager.retire(key)
    return {"status": "retired", "key": key, "reason": reason}


def tool_get_memories(query: str) -> dict:
    results = memory_manager.search(query, limit=5)
    if not results:
        return {"status": "empty", "count": 0}
    return {"status": "found", "count": len(results), "memories": results}
