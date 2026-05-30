"""Layer 1 — Router.

Parses incoming Telegram messages, picks the model key and clean text,
delegates to agent.respond(). Only parses and delegates: no Telegram,
PTB, OpenRouter, or direct SQLite (db.py only).
"""

import uuid
import time
import subprocess

from core.agent import respond, get_last_model
from core.db import (
    create_thread, list_memories, list_threads,
    get_last_stable_commit, get_last_deploy, get_deploy_history,
)
from core.report import report
from core.model_manager import get_status_report, get_throttled_models
from core.rate_limits import rate_limits
from core.polling import polling_manager
from tools.goals import (
    get_goals_list,
    get_goal_detail,
    get_current_plan,
    get_tasks_today,
    update_task,
    update_task_status,
    get_milestone,
)

_current_threads: dict[int, str] = {}
_ROUTER_STARTUP = time.time()


def handle_status() -> str:
    """Return bot status: uptime, memory count, deploy info, model status."""
    uptime = time.time() - _ROUTER_STARTUP
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    uptime_str = f"{hours}h {minutes}m" if hours else f"{minutes}m"

    memories = list_memories()
    threads = list_threads()
    last_model = get_last_model()
    throttled = get_throttled_models()
    last_deploy = get_last_deploy()
    stable = get_last_stable_commit()
    history = get_deploy_history(limit=100)
    deploy_count = sum(1 for d in history if not d["rolled_back"])
    rollback_count = sum(1 for d in history if d["rolled_back"])

    lines = [
        "📊 PrivyBot Status",
        f"Uptime: {uptime_str}",
        f"Memories: {len(memories)}",
        f"Threads: {len(threads)}",
        f"Last model: {last_model}",
        f"Throttled models: {len(throttled)}",
    ]

    # Rate limit status
    status_data = rate_limits.get_status()
    limited = [s for s in status_data if not s["available"]]
    if limited:
        lines.append(f"⚠️ Rate limited: {', '.join(l['api'] for l in limited)}")
    elif status_data:
        lines.append("✅ All APIs available")

    # Polling status
    poll_status = polling_manager.status()
    in_progress = [p for p in poll_status if p["in_progress"]]
    overdue = [p for p in poll_status if p["overdue"]]

    if in_progress:
        keys = [p["key"] for p in in_progress]
        lines.append(f"🔄 Polling: {', '.join(keys)}")
    elif overdue:
        keys = [p["key"] for p in overdue]
        lines.append(f"⚠️ Overdue polls: {', '.join(keys)}")
    elif poll_status:
        lines.append("✅ All polls current")

    if last_deploy:
        lines.append(f"\nCurrent commit: {last_deploy['commit_hash'][:7] if last_deploy['commit_hash'] else 'unknown'}")
        lines.append(f"  \"{last_deploy['commit_message']}\"")
        lines.append(f"  Deployed: {last_deploy['deployed_at']}")
    if stable and last_deploy and stable["id"] != last_deploy["id"]:
        lines.append(f"Last stable: {stable['commit_hash'][:7] if stable['commit_hash'] else 'unknown'}")
    lines.append(f"Deploys: {deploy_count}  Rollbacks: {rollback_count}")

    if throttled:
        lines.append("\nThrottled:")
        for m in throttled[:5]:
            lines.append(f"  • {m}")
        if len(throttled) > 5:
            lines.append(f"  ... and {len(throttled) - 5} more")
    return "\n".join(lines)


async def _ensure_thread(chat_id: int) -> str:
    if chat_id not in _current_threads:
        thread_id = str(uuid.uuid4())
        create_thread(thread_id)
        _current_threads[chat_id] = thread_id
        await report("thread_new")
    return _current_threads[chat_id]


async def handle_new(chat_id: int) -> None:
    thread_id = str(uuid.uuid4())
    create_thread(thread_id)
    _current_threads[chat_id] = thread_id
    await report("thread_new")


def handle_memories(chat_id: int) -> str:
    memories = list_memories()
    if not memories:
        return "No memories yet."
    by_layer: dict[str, list] = {}
    for m in memories:
        by_layer.setdefault(m["layer"], []).append(m)
    lines = ["🧠 What I know:"]
    for layer in sorted(by_layer):
        lines.append(f"\n[{layer}]")
        for m in by_layer[layer]:
            lines.append(f"• {m['key']}: {m['content']}")
    return "\n".join(lines)


def help_text() -> str:
    return (
        "PrivyBot commands:\n"
        "/think [msg] — DeepSeek (structured)\n"
        "/claude [msg] — Claude Sonnet\n"
        "/new — start fresh thread\n"
        "/memories — list what I know\n"
        "/models — free model availability\n"
        "/status — bot status\n"
        "/deploy — pull main and restart (Tower only)\n"
        "/rollback — revert to last stable commit\n"
        "/history — show recent deploy history\n"
        "/goals — list active goals\n"
        "/goal [id] — show goal details\n"
        "/tasks — show this week's tasks\n"
        "/tasks today — show today's tasks\n"
        "/task done [id] — mark task complete\n"
        "/plan — show current week plan\n"
        "/confirm [id] — confirm milestone complete\n"
        "/reject [id] — dismiss suggestion\n"
        "/todo — today's personal tasks\n"
        "/todo list — all pending tasks\n"
        "/todo week — this week's tasks\n"
        "/todo done [id] — mark task done\n"
        "/todo add [text] — quick capture\n"
        "/sync — sync with Google Tasks\n"
        "/help — this message"
    )


def handle_goals() -> str:
    """Handle /goals command — list active goals."""
    result = get_goals_list(status="active")
    if "error" in result:
        return result["error"]
    
    lines = ["🎯 Active Goals:"]
    for goal in result["goals"]:
        lines.append(f"\n• {goal['title']} ({goal['progress_pct']}%)")
        lines.append(f"  Deadline: {goal['deadline']}")
        for milestone in goal.get("milestones", []):
            status_icon = "✓" if milestone["status"] == "complete" else "○"
            lines.append(f"  {status_icon} {milestone['title']}")
    
    return "\n".join(lines)


def handle_goal(goal_id: str) -> str:
    """Handle /goal [id] command — show goal details."""
    result = get_goal_detail(goal_id)
    if "error" in result:
        return result["error"]
    
    goal = result
    lines = [
        f"🎯 {goal['title']}",
        f"Progress: {goal['progress_pct']}%",
        f"Deadline: {goal['deadline']}",
        f"Status: {goal['status']}",
    ]
    
    if goal.get("description"):
        lines.append(f"\n{goal['description']}")
    
    lines.append("\nMilestones:")
    for milestone in goal.get("milestones", []):
        status_icon = "✓" if milestone["status"] == "complete" else "○"
        lines.append(f"  {status_icon} {milestone['title']} — {milestone['deadline']}")
        
        for task in milestone.get("tasks", []):
            task_icon = "✓" if task["status"] == "complete" else "○"
            lines.append(f"    {task_icon} {task['title']}")
    
    return "\n".join(lines)


def handle_tasks(filter_today: bool = False) -> str:
    """Handle /tasks command — show tasks."""
    if filter_today:
        result = get_tasks_today()
        header = "📋 Today's Tasks:"
    else:
        result = get_current_plan()
        if "error" in result:
            return result["error"]
        header = f"📋 This Week's Tasks ({result['plan']['focus']}):"
        result = {"tasks": result["tasks"]}
    
    if "error" in result:
        return result["error"]
    
    lines = [header]
    for task in result["tasks"]:
        status_icon = "✓" if task["status"] == "complete" else "○"
        lines.append(f"\n{status_icon} {task['title']}")
        lines.append(f"  Due: {task['due_date']}")
        if task.get("scheduled_at"):
            lines.append(f"  Scheduled: {task['scheduled_at']}")
    
    return "\n".join(lines)


def handle_task_done(task_id: str) -> str:
    """Handle /task done [id] command — mark task complete."""
    result = update_task(task_id, "complete")
    if "error" in result:
        return result["error"]
    
    return f"✓ Task marked complete: {result['title']}"


def handle_plan() -> str:
    """Handle /plan command — show current week plan."""
    result = get_current_plan()
    if "error" in result:
        return result["error"]
    
    plan = result["plan"]
    lines = [
        f"📅 Week: {plan['week_start']} to {plan['week_end']}",
        f"Focus: {plan['focus']}",
    ]
    
    if plan.get("notes"):
        lines.append(f"Notes: {plan['notes']}")
    
    lines.append(f"\nTasks: {len(result['tasks'])}")
    for task in result["tasks"]:
        status_icon = "✓" if task["status"] == "complete" else "○"
        lines.append(f"  {status_icon} {task['title']} — {task['due_date']}")
    
    return "\n".join(lines)


def handle_confirm(milestone_id: str) -> str:
    """Handle /confirm [id] command — mark milestone complete."""
    milestone = get_milestone(milestone_id)
    if not milestone:
        return f"Milestone not found: {milestone_id}"
    
    from core.db import upsert_milestone
    upsert_milestone(
        milestone_id=milestone_id,
        goal_id=milestone["goal_id"],
        title=milestone["title"],
        deadline=milestone["deadline"],
        status="complete",
        notes=milestone.get("notes"),
    )
    
    return f"✓ Milestone marked complete: {milestone['title']}"


def handle_todo(sub: str, rest: str) -> str:
    """Handle /todo subcommands — list, done. add is handled in route()."""
    from tools.personal import list_personal_tasks, complete_personal_task

    if sub == "list":
        result = list_personal_tasks(filter="all")
    elif sub == "week":
        result = list_personal_tasks(filter="upcoming")
    elif sub == "done" and rest:
        try:
            r = complete_personal_task(int(rest.strip()))
            if "error" in r:
                return r["error"]
            out = f"\u2713 Done: {r['title']}"
            if r.get("next_due"):
                out += f"\n\u21bb Next: {r['next_due']}"
            return out
        except Exception as e:
            return f"Error: {e}"
    else:
        result = list_personal_tasks(filter="today")

    if result["count"] == 0:
        return f"No personal tasks ({result['filter']})."

    lines = [f"\U0001f4dd Personal tasks ({result['filter']}) \u2014 {result['count']}:"]
    for t in result["tasks"]:
        line = f"  [{t['id']}] {t['title']}"
        if t.get("due_time"):
            line += f" at {t['due_time']}"
        elif t.get("due_date"):
            line += f" ({t['due_date']})"
        if t.get("recurrence"):
            line += f" \u21bb"
        lines.append(line)
    return "\n".join(lines)


def handle_reject(milestone_id: str) -> str:
    """Handle /reject [id] command — dismiss suggestion."""
    return f"Dismissed suggestion for milestone: {milestone_id}"


def handle_sync() -> str:
    """Handle /sync command — run Google Tasks sync manually."""
    from tools.sync_tasks import run_sync
    result = run_sync()
    if result.get("status") == "error":
        return f"Sync error: {result.get('error', 'unknown')}"
    return (
        f"\U0001f504 Synced \u2014 "
        f"pulled {result['pulled_new']}, "
        f"pushed {result['pushed_new']} new, "
        f"{result['pushed_completions']} completions"
    )


async def handle_deploy(chat_id: int) -> str:
    """Handle /deploy command — run deploy script as subprocess."""
    await report("tool_called", tool_name="deploy", result_summary="Starting deploy...")
    
    try:
        result = subprocess.run(
            ["uv", "run", "python", "scripts/deploy.py"],
            capture_output=True,
            text=True,
            timeout=120
        )
        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip()
        return output or "Deploy completed."
    except subprocess.TimeoutExpired:
        return "Deploy timed out after 2 minutes."
    except Exception as e:
        return f"Deploy failed: {str(e)}"


async def handle_rollback(chat_id: int) -> str:
    """Handle /rollback command — run rollback script as subprocess."""
    await report("tool_called", tool_name="rollback", result_summary="Starting rollback...")

    try:
        result = subprocess.run(
            ["uv", "run", "python", "scripts/rollback.py"],
            capture_output=True,
            text=True,
            timeout=120
        )
        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip()
        return output or "Rollback completed."
    except subprocess.TimeoutExpired:
        return "Rollback timed out after 2 minutes."
    except Exception as e:
        return f"Rollback failed: {str(e)}"


def handle_history() -> str:
    """Handle /history command — show recent deploy history."""
    records = get_deploy_history(limit=5)
    if not records:
        return "No deploy history yet."

    lines = ["📋 Deploy history:"]
    for d in records:
        if d["rolled_back"]:
            icon = "↩️"
        elif d["stable"]:
            icon = "✅"
        elif d["verify_passed"]:
            icon = "⚠️"
        else:
            icon = "🔴"
        short_hash = d["commit_hash"][:7] if d["commit_hash"] else "unknown"
        msg = d["commit_message"] or ""
        deployed_at = d["deployed_at"] or ""
        lines.append(f"{icon} {short_hash} — {msg} ({deployed_at[:10]})")
    return "\n".join(lines)


async def route(chat_id: int, text: str) -> str:
    if not text or not text.strip():
        return "Say something."

    text = text.strip()

    if text == "/new" or text.startswith("/new"):
        await handle_new(chat_id)
        return "New thread started."
    if text == "/memories" or text.startswith("/memories"):
        return handle_memories(chat_id)
    if text == "/models" or text.startswith("/models"):
        return get_status_report()
    if text == "/status" or text.startswith("/status"):
        return handle_status()
    if text == "/deploy" or text.startswith("/deploy"):
        return await handle_deploy(chat_id)
    if text == "/rollback" or text.startswith("/rollback"):
        return await handle_rollback(chat_id)
    if text == "/history" or text.startswith("/history"):
        return handle_history()
    if text == "/help" or text.startswith("/help"):
        return help_text()
    
    # Goals commands
    if text == "/goals" or text.startswith("/goals"):
        return handle_goals()
    if text.startswith("/goal "):
        goal_id = text[len("/goal "):].strip()
        return handle_goal(goal_id)
    if text == "/tasks" or text.startswith("/tasks"):
        if text == "/tasks today":
            return handle_tasks(filter_today=True)
        return handle_tasks(filter_today=False)
    if text.startswith("/task done "):
        task_id = text[len("/task done "):].strip()
        return handle_task_done(task_id)
    if text == "/plan" or text.startswith("/plan"):
        return handle_plan()
    if text.startswith("/confirm "):
        milestone_id = text[len("/confirm "):].strip()
        return handle_confirm(milestone_id)
    if text.startswith("/reject "):
        milestone_id = text[len("/reject "):].strip()
        return handle_reject(milestone_id)
    if text == "/sync" or text.startswith("/sync"):
        return handle_sync()
    if text == "/todo" or text.startswith("/todo"):
        parts = text[len("/todo"):].strip().split(None, 1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""
        if sub == "add" and rest:
            thread_id = await _ensure_thread(chat_id)
            return await respond(f"Add personal task: {rest}", thread_id)
        return handle_todo(sub, rest)

    if text.startswith("/think"):
        model_key, message = "think", text[len("/think"):].strip()
    elif text.startswith("/claude"):
        model_key, message = "claude", text[len("/claude"):].strip()
    else:
        model_key, message = "default", text

    if not message:
        return "Say something."

    thread_id = await _ensure_thread(chat_id)
    return await respond(message, thread_id, model_key)
