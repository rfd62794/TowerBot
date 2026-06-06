"""Layer 4 — Memory.

Wraps memory_manager with agent-facing tool functions and their OpenRouter
tool definitions. Only the Agent layer calls these.
Pure memory logic: no Telegram, OpenRouter, routing, or report code.
"""

from infra.memory_manager import memory_manager

VALID_LAYERS = {"technical", "project", "personal", "business", "content"}


def tool_save_memory(key: str, content: str = None, layer: str = "project", value: str = None) -> dict:
    actual_content = content or value or ""
    if layer not in VALID_LAYERS:
        return {"status": "error", "reason": f"invalid layer '{layer}'"}
    memory_manager.save(key, actual_content, layer)
    return {"status": "saved", "key": key, "layer": layer, "content": actual_content}


def tool_update_memory(key: str, content: str, reason: str) -> dict:
    memory_manager.update(key, content)
    return {"status": "updated", "key": key, "reason": reason, "content": content}


def tool_retire_memory(key: str, reason: str) -> dict:
    memory_manager.retire(key)
    return {"status": "retired", "key": key, "reason": reason}


def tool_get_memories(query: str = None, q: str = None, **kwargs) -> dict:
    actual_query = query or q or ""
    if not actual_query:
        return {"ok": False, "error": "query required"}
    results = memory_manager.search(actual_query, limit=5)
    if not results:
        return {"status": "empty", "count": 0}
    return {"status": "found", "count": len(results), "memories": results}
