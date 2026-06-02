"""Autonomous task runner — scheduled agent execution without user presence."""

import os
import time
import logging
import random
import psutil
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.agent import respond
from bot.task_runner import resolve_task, get_all_resolved_tasks, get_task_model_role
from bot.model_helpers import call_openrouter
from infra.model_router import route
from infra.db.autonomous import record_agent_action, get_recent_task_actions
from infra.db.system_metrics import record_system_snapshot
from infra.db.bot_state import get_dev_mode
from infra.db.task_queue import get_due_tasks, mark_running, mark_complete, mark_failed
from scripts.update import check_for_updates
from infra.chain.observer import observe_completed_chains

logger = logging.getLogger("privy.autonomous")


def record_system_snapshot_task():
    """Record current system resources to database."""
    try:
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        cpu = psutil.cpu_percent(interval=0.1)
        
        # Get Ollama info if available
        ollama_model = None
        ollama_ram_gb = None
        try:
            import os
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            response = requests.get(f"{host}/api/ps", timeout=5)
            if response.status_code == 200:
                data = response.json()
                ollama_model = data.get("model")
                ollama_ram_gb = round(data.get("vm_rss", 0) / (1024**3), 2)
        except Exception:
            pass  # Ollama not available
        
        record_system_snapshot(
            ram_used_gb=round(ram.used / (1024**3), 2),
            ram_free_gb=round(ram.available / (1024**3), 2),
            disk_free_gb=round(disk.free / (1024**3), 2),
            cpu_percent=cpu,
            ollama_model=ollama_model,
            ollama_ram_gb=ollama_ram_gb
        )
        
        logger.info(f"System snapshot recorded: {ram.available / (1024**3):.2f}GB RAM free")
    except Exception as e:
        logger.error(f"Failed to record system snapshot: {e}")


# Fallback micro-tasks for when primary tasks find nothing
FALLBACK_TASKS = [
    # Post builder — runs as primary fallback, advances one stage
    (
        "Call advance_post_pipeline() to advance the most in-progress blog post "
        "by exactly one stage. Use the research, skeleton writing, and "
        "create_draft_from_pipeline tools as instructed by the pipeline. "
        "Report what stage was completed."
    ),
    # Variety fallbacks for when post is at stage 4 (waiting for Robert)
    (
        "Update one stale metric in memory (anything with a date older than 3 days "
        "that can be refreshed with available tools). Update with fresh value + date."
    ),
    (
        "Find one correlation between this week's commits and itch.io or YouTube data. "
        "One specific finding. Save as memory 'Weekly insight: [date] — [finding]'."
    ),
    (
        "Read ROADMAP next steps. Pick the smallest incomplete item. Write two sentences: "
        "what it is and what specifically blocks it. "
        "Save as memory 'Build context: [item]'."
    ),
    (
        "Check get_pypi_stats for openagent-directive. Compare to baseline "
        "(openagent_pypi_baseline memory). Note any change. "
        "Save as memory 'OpenAgent check: [date] — [finding]'. "
        "If >50% day-over-day increase: mark URGENT."
    ),
]


async def run_autonomous_task(task_name: str, send_fn):
    """
    Execute a single autonomous task.

    Args:
        task_name: Task name from config/tasks.yaml
        send_fn: Async function to send Telegram messages
    """
    # Check dev mode for production instances
    instance_role = os.environ.get("INSTANCE_ROLE", "development")
    if instance_role == "production" and get_dev_mode():
        logger.info(f"Skipping {task_name} — dev mode active")
        return

    try:
        task = resolve_task(task_name)
    except ValueError as e:
        logger.error(f"Failed to resolve task {task_name}: {e}")
        return

    if not task.get("enabled"):
        logger.debug(f"Task disabled: {task_name}")
        return

    # Build prompt: persona prefix + template body
    prefix = (
        "[AUTONOMOUS MODE — Robert is not present. "
        "Take action directly. Do not ask clarifying questions. "
        "Never delete data, never send emails. "
        "Begin summary with URGENT: or DONE:]\n\n"
    )
    full_prompt = f"{prefix}{task['persona']}\n\n{task['prompt']}"

    start = time.time()
    result = ""
    urgent = 0

    try:
        result = await respond(
            full_prompt,
            thread_id=f"autonomous_{task_name}",
            max_iter=task['max_iterations']
        )
        duration_ms = int((time.time() - start) * 1000)

        # Check if result is urgent
        if result.upper().startswith("URGENT:"):
            urgent = 1

        # urgent_on check from task type
        if task.get('urgent_on'):
            if any(kw in result.lower() for kw in task['urgent_on']):
                urgent = 1

        record_agent_action(task_name, result, duration_ms, urgent)
        logger.info(f"Task {task_name} completed in {duration_ms}ms")

        # Send urgent notification via Telegram
        if urgent:
            await send_fn(f"🚨 {task_name}:\n{result[:500]}")

        # Fallback: consecutive empty runs trigger a micro-task
        if task.get('fallback_on_empty'):
            nothing_phrases = [
                "0 mentions", "0 found", "nothing important",
                "no urgent", "no changes detected", "nothing new"
            ]
            if any(p in result.lower() for p in nothing_phrases):
                recent_empty = _count_recent_empty_runs(task_name, hours=8)
                if recent_empty >= 2:
                    # 60% chance of post builder, 40% chance of variety task
                    if random.random() < 0.6:
                        fallback = FALLBACK_TASKS[0]  # post builder
                    else:
                        fallback = random.choice(FALLBACK_TASKS[1:])  # variety
                    fallback_result = await respond(
                        f"[MICRO-TASK triggered by {task_name} finding nothing]\n\n"
                        f"{fallback}",
                        thread_id="autonomous_fallback",
                        max_iter=10
                    )
                    record_agent_action("fallback", fallback_result)
                    logger.info(f"Fallback micro-task triggered by {task_name}")

    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        error_msg = f"ERROR: {str(e)}"
        record_agent_action(task_name, error_msg, duration_ms, 0)
        logger.error(f"Task {task_name} failed: {e}")


def _count_recent_empty_runs(task_name: str, hours: int = 8) -> int:
    """Count how many recent runs of this task found nothing."""
    actions = get_recent_task_actions(task_name, hours=hours)
    nothing_phrases = [
        "0 mentions", "0 found", "nothing important",
        "no urgent", "no changes detected", "nothing new"
    ]
    count = 0
    for action in actions:
        result = (action.get("result") or "").lower()
        if any(p in result for p in nothing_phrases):
            count += 1
    return count


async def process_delegation_queue(send_fn) -> None:
    """
    Poll task_queue for due delegated tasks.
    Executes each via model_router if task has model_role, else agent.respond().
    INSTANCE_ROLE check: only production instances process queue.
    """
    instance_role = os.environ.get("INSTANCE_ROLE", "development")
    if instance_role != "production":
        return

    due = get_due_tasks(limit=3)  # max 3 per poll cycle
    
    for task in due:
        mark_running(task["id"])
        start = time.time()

        # Guard: skip legacy tasks with NULL prompt
        if task.get("prompt") is None:
            mark_failed(task["id"], "legacy task — predates prompt schema")
            logger.warning(f"[delegation] task {task['id']} has NULL prompt, skipping")
            continue

        try:
            full_prompt = (
                "[DELEGATED TASK — requested by Claude]\n\n"
                f"{task['prompt']}"
            )
            if task.get("message"):  # context field
                full_prompt += f"\n\nContext: {task['message']}"
            
            # Check if task has a model_role for routing
            task_name = task.get("task_name", "delegated")
            model_role = get_task_model_role(task_name)
            
            if model_role:
                # Use model_router for tasks with defined model_role
                logger.info(f"[delegation] task {task['id']} using model_router with role: {model_role}")
                routed = route(
                    role=model_role,
                    call_fn=call_openrouter,
                    prompt=full_prompt
                )
                result = routed["result"]
            else:
                # Fall back to agent.respond() for tasks without model_role
                logger.info(f"[delegation] task {task['id']} using agent.respond() (no model_role)")
                result = await respond(
                    full_prompt,
                    thread_id=f"delegation_{task['id']}",
                    max_iter=25  # autonomous max iterations
                )
            
            duration_ms = int((time.time() - start) * 1000)
            mark_complete(task["id"], result, duration_ms)
            
            # Mirror to agent_actions for unified history
            record_agent_action(
                task_name=task_name,
                result=result,
                duration_ms=duration_ms,
                source="delegated",
                source_task_id=task["id"]
            )
            
            # Alert if urgent
            if task["priority"] == "urgent":
                await send_fn(
                    f"🚨 Delegated task complete:\n{result[:500]}"
                )
        
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            mark_failed(task["id"], str(e))
            logger.error(f"[delegation] task {task['id']} failed: {e}")


def setup_autonomous_scheduler(scheduler: AsyncIOScheduler, send_fn):
    """
    Register autonomous tasks with APScheduler.

    Args:
        scheduler: AsyncIOScheduler instance
        send_fn: Async function to send Telegram messages
    """
    for task in get_all_resolved_tasks():
        schedule = task['schedule']
        task_name = task['name']

        if schedule['type'] == 'interval':
            scheduler.add_job(
                run_autonomous_task,
                "interval",
                minutes=schedule['minutes'],
                args=[task_name, send_fn],
                id=task_name,
                max_instances=1,
                replace_existing=True,
            )
            logger.info(f"Registered interval task: {task_name} every {schedule['minutes']}min")

        elif schedule['type'] == 'cron':
            job_kwargs = {
                "hour": schedule['hour'],
                "minute": schedule['minute'],
                "args": [task_name, send_fn],
                "id": task_name,
                "max_instances": 1,
                "replace_existing": True,
            }
            if 'day_of_week' in schedule:
                job_kwargs["day_of_week"] = schedule['day_of_week']
            scheduler.add_job(
                run_autonomous_task,
                "cron",
                **job_kwargs
            )
            day_str = f" day {schedule['day_of_week']}" if 'day_of_week' in schedule else ""
            logger.info(f"Registered cron task: {task_name} at {schedule['hour']:02d}:{schedule['minute']:02d}{day_str}")

    # Register delegation queue poll
    scheduler.add_job(
        process_delegation_queue,
        "interval",
        seconds=60,
        id="delegation_poll",
        max_instances=1,
        kwargs={"send_fn": send_fn}
    )
    logger.info("Registered delegation poll: every 60 seconds")

    # Register auto-update check
    scheduler.add_job(
        check_for_updates,
        "interval",
        minutes=30,
        id="auto_update_check",
        max_instances=1,
        kwargs={"send_fn": send_fn}
    )
    logger.info("Registered auto-update check: every 30 minutes")

    # Register chain observer job
    scheduler.add_job(
        observe_completed_chains,
        "interval",
        minutes=30,
        id="chain_observer",
        max_instances=1,
        replace_existing=True
    )
    logger.info("Registered chain observer: every 30 minutes")

    # Register weekly digest job
    async def send_weekly_digest(send_fn):
        """Sunday morning digest of chain activity and promotion candidates."""
        from infra.chain.observer import get_promotion_candidates
        from infra.db.chains import list_chains

        completed = list_chains(status='complete')
        failed = list_chains(status='failed')
        candidates = get_promotion_candidates()

        lines = ["📊 <b>Weekly Chain Digest</b>\n"]
        lines.append(f"Chains completed: {len(completed)}")
        lines.append(f"Chains failed: {len(failed)}")

        if candidates:
            lines.append(f"\n🔁 <b>Promotion candidates ({len(candidates)}):</b>")
            for c in candidates[:5]:
                lines.append(
                    f"  • {c['step_sequence_hash'][:8]} — "
                    f"{c['observed_count']} uses, "
                    f"{c['success_rate']:.0%} success"
                )
        else:
            lines.append("\nNo promotion candidates yet.")

        message = "\n".join(lines)
        await send_fn(message)

    scheduler.add_job(
        send_weekly_digest,
        "cron",
        day_of_week='sun',
        hour=8,
        minute=0,
        id='weekly_digest',
        max_instances=1,
        args=[send_fn],
        replace_existing=True
    )
    logger.info("Registered weekly digest: Sunday 08:00")
