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
    {
        "type": "function",
        "function": {
            "name": "get_goals",
            "description": "Get list of goals with optional status filter. "
                           "Use to check progress on long-term objectives.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "complete", "paused"],
                        "description": "Optional status filter"
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_goal",
            "description": "Get detailed information about a specific goal including milestones and tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal_id": {"type": "string", "description": "Goal ID (e.g., palm_beach_2036)"},
                },
                "required": ["goal_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_plan",
            "description": "Get current weekly plan with focus and associated tasks.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tasks_today",
            "description": "Get tasks due today.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_tasks",
            "description": "Get upcoming scheduled tasks within specified hours.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "description": "Hours to look ahead (default: 24)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update task status. Use when user reports completing a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID"},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "complete", "cancelled"],
                    },
                },
                "required": ["task_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a new task to the current week plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "due_date": {"type": "string", "description": "Due date (YYYY-MM-DD)"},
                    "scheduled_at": {"type": "string", "description": "Optional scheduled datetime (YYYY-MM-DD HH:MM)"},
                    "milestone_id": {"type": "string", "description": "Optional milestone ID to link to"},
                },
                "required": ["title", "due_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_goal_progress",
            "description": "Suggest goal progress update based on milestone. "
                           "Returns suggestion text for Telegram. Does NOT update — agent suggests only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "milestone_id": {"type": "string", "description": "Milestone ID"},
                },
                "required": ["milestone_id"],
            },
        },
    },
]
