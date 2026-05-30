"""Layer 4 — Memory.

Wraps db.py with agent-facing tool functions and their OpenRouter
tool definitions. Only the Agent layer calls these.
Pure memory logic: no Telegram, OpenRouter, routing, or report code.
"""

from core.db import save_memory, update_memory, retire_memory, get_memories
from tools.goals import (
    get_goals_list,
    get_goal_detail,
    get_current_plan,
    get_tasks_today,
    get_upcoming_tasks,
    update_task,
    add_new_task,
    suggest_goal_progress,
)

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


# Goals tool wrappers
def tool_get_goals(status: str = None) -> dict:
    return get_goals_list(status=status)


def tool_get_goal(goal_id: str) -> dict:
    return get_goal_detail(goal_id)


def tool_get_current_plan() -> dict:
    return get_current_plan()


def tool_get_tasks_today() -> dict:
    return get_tasks_today()


def tool_get_upcoming_tasks(hours: int = 24) -> dict:
    return get_upcoming_tasks(hours=hours)


def tool_update_task(task_id: str, status: str) -> dict:
    return update_task(task_id, status)


def tool_add_task(title: str, due_date: str, scheduled_at: str = None, milestone_id: str = None) -> dict:
    return add_new_task(title, due_date, scheduled_at, milestone_id)


def tool_suggest_goal_progress(milestone_id: str) -> dict:
    return suggest_goal_progress(milestone_id)
