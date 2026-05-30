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
            "description": "WHEN: Robert states a fact about himself, his projects, preferences, decisions, goals, people he mentions, or technical choices. Specific triggers: 'I'm working on X', 'I prefer Y', 'my Z is...', 'I decided to...', 'remember that...'. Save after learning anything that should persist across conversations.\n\nRETURNS: status ('saved'), key, layer, content.\n\nDO NOT CALL: for casual conversation, temporary context, things said in passing, or information already in memory. Check get_memories first if unsure whether something is already saved.\n\nNEVER save commitments as memories. When Robert says he WILL do something with a time reference ('I'm going to X by Y', 'I'll do X this weekend') — acknowledge it explicitly in your response and ask him to confirm so it can be tracked. Example: 'Got it — you're planning to record Raccoin after June 15. Want me to add that as a task?'\n\nLAYERS: technical — stack, tools, languages, patterns. project — active projects and their status. personal — life context, family, goals, style. business — work, clients, income, career. content — YouTube, games, series, schedule.",
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
            "description": "WHEN: Robert corrects something you said, a fact has changed, a project status changed, a preference shifted. Triggers: 'actually it's...', 'that changed', 'I moved to...', 'we decided...', 'no longer...'. Update IMMEDIATELY when corrected. Do not wait or ask for confirmation.\n\nRETURNS: status ('updated'), key, reason, content.\n\nDO NOT CALL: to create new memory — use save_memory instead. Requires an existing key to update.",
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
            "description": "WHEN: A memory is no longer true and updating it would be misleading. Use when a project is abandoned, a fact is fully obsolete, or a preference no longer applies at all.\n\nRETURNS: status ('retired'), key, reason.\n\nDO NOT CALL: when information just changed — use update_memory instead. Retire only when the memory should stop being referenced entirely.",
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
            "description": "WHEN: Starting a new topic, answering a question about Robert's projects or preferences, before save_memory to check if key already exists. Call at the start of any conversation about a specific project or goal.\n\nRETURNS: status ('found'/'empty'), count (int), memories list — each with key, content, layer. Returns up to 5 closest matches.\n\nDO NOT CALL: for every single message. Call when context is needed, not reflexively. If you already retrieved memories this conversation on this topic — use them.",
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
            "description": "WHEN: User asks about goals, long-term plans, 'what am I working toward', progress, 'Palm Beach', 'ReactReel', any goal by name. Also call when user asks 'what should I prioritize'.\n\nRETURNS: List of goals each with id, title, deadline, status, progress_pct, notes. Filter by status if needed.\n\nDO NOT CALL: for this week's tasks — use get_current_plan or get_tasks_today. Goals are long-term objectives only.",
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
            "description": "WHEN: User asks about a specific goal in detail, milestones for a goal, 'what's left for X', progress breakdown, or after get_goals when user wants to drill into one goal.\n\nRETURNS: Full goal object with milestones list (each with id, title, deadline, status) and associated tasks.\n\nDO NOT CALL: for the goals list — use get_goals instead. Requires a specific goal_id.",
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
            "description": "WHEN: User asks what the plan is this week, 'what am I focused on', 'what's the weekly plan', or when giving context about current priorities.\n\nRETURNS: week_start, week_end, focus (string), notes, tasks list for this week.\n\nDO NOT CALL: for today's specific tasks — use get_tasks_today for that. This is the weekly overview.",
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
            "description": "WHEN: User asks what to do today, today's tasks, 'what's on my list', morning planning, or any question about today's specific items.\n\nRETURNS: List of tasks each with id, title, due_date, status, scheduled_at. Filtered to today only.\n\nDO NOT CALL: for the weekly plan — use get_current_plan instead. Do not call for upcoming tasks beyond today — use get_upcoming_tasks.",
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
            "description": "WHEN: User asks what's coming up, tasks in the next few days, upcoming scheduled items, 'what do I have this week', forward-looking task questions.\n\nRETURNS: List of tasks due within specified hours, each with id, title, due_date, scheduled_at, status.\n\nDO NOT CALL: for today's tasks — use get_tasks_today instead. Default 24 hours covers tomorrow.",
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
            "description": "WHEN: User says they completed a task, 'I finished X', 'done with Y', 'mark X complete', task status changed. Requires task_id — get it from get_tasks_today or get_upcoming_tasks first.\n\nRETURNS: status ('updated'), task_id, new_status, title.\n\nDO NOT CALL: without a valid task_id. Never guess a task_id. Always retrieve tasks first to get the ID.",
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
            "description": "WHEN: User wants to add something to their plan, 'add a task', 'remind me to', 'I need to do X by Y', creating a new to-do item.\n\nRETURNS: status ('created'), task_id, title, due_date.\n\nDO NOT CALL: for commitments with vague deadlines — save to memory instead. Use only when there's a clear title and due date to work with.",
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
            "description": "WHEN: User describes completing something that sounds like a milestone — 'I shipped the OAuth', 'I got my first customer', 'I deployed to Tower'. This does NOT update anything. It generates a suggestion string that gets sent to Telegram for confirmation. User must /confirm or /reject.\n\nRETURNS: suggestion text string for display. Does not modify any data.\n\nDO NOT CALL: to actually update goals — this is suggestion only. Never call without a milestone_id. Get milestone_id from get_goal first.",
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
