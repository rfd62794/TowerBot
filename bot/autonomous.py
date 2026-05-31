"""Autonomous task runner — scheduled agent execution without user presence."""

import time
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.agent import respond
from infra.db.autonomous import record_agent_action

logger = logging.getLogger("privy.autonomous")

# Task definitions with schedules and prompts
TASKS = {
    "email_triage": {
        "schedule_type": "interval",
        "interval_minutes": 120,
        "enabled": True,
        "prompt": (
            "Check both email inboxes (personal + RFD IT) for unread messages. "
            "For any that look important or require a response, create a personal task. "
            "Report: how many emails checked, what tasks created (if any)."
        ),
    },
    "nightly_snapshot": {
        "schedule_type": "cron",
        "hour": 23,
        "minute": 30,
        "enabled": True,
        "prompt": (
            "Pull today's YouTube channel summary and VoidDrift itch.io stats. "
            "Save a memory entry: 'Daily metrics YYYY-MM-DD' with key numbers. "
            "Note any significant change from yesterday."
        ),
    },
    "itch_reddit_check": {
        "schedule_type": "interval",
        "interval_minutes": 30,
        "enabled": True,
        "prompt": (
            "Search r/incremental_games and r/gamedev for 'VoidDrift'. "
            "If any mentions found in last 24 hours: save as memory, mark URGENT. "
            "Report what you found."
        ),
    },
    "openagent_momentum_tracker": {
        "schedule_type": "cron",
        "hour": 8,
        "minute": 0,
        "enabled": True,
        "prompt": (
            "Check download stats for openagent-directive on PyPI using get_pypi_stats. "
            "Compare to the last saved count in memory (key: 'OpenAgent stats'). "
            "If week-over-week downloads increased >20%: save to memory, mark URGENT. "
            "Save current stats as memory 'OpenAgent stats YYYY-MM-DD'. "
            "Report: last_week count, change from prior week, trend direction."
        ),
    },
}


async def run_autonomous_task(task_name: str, send_fn):
    """
    Execute a single autonomous task.

    Args:
        task_name: Key from TASKS dict
        send_fn: Async function to send Telegram messages
    """
    task = TASKS.get(task_name)
    if not task:
        logger.error(f"Unknown task: {task_name}")
        return

    if not task.get("enabled"):
        logger.debug(f"Task disabled: {task_name}")
        return

    prefix = (
        "[AUTONOMOUS MODE — Robert is not present. "
        "Take action directly. Do not ask clarifying questions. "
        "Never delete data, never send emails. "
        "Begin summary with URGENT: or DONE:]\n\n"
    )

    start = time.time()
    result = ""
    urgent = 0

    try:
        result = await respond(
            prefix + task["prompt"],
            thread_id=f"autonomous_{task_name}"
        )
        duration_ms = int((time.time() - start) * 1000)

        # Check if result is urgent
        if result.upper().startswith("URGENT:"):
            urgent = 1

        record_agent_action(task_name, result, duration_ms, urgent)
        logger.info(f"Task {task_name} completed in {duration_ms}ms")

        # Send urgent notification via Telegram
        if urgent:
            await send_fn(f"🚨 {task_name}:\n{result[:500]}")

    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        error_msg = f"ERROR: {str(e)}"
        record_agent_action(task_name, error_msg, duration_ms, 0)
        logger.error(f"Task {task_name} failed: {e}")


def setup_autonomous_scheduler(scheduler: AsyncIOScheduler, send_fn):
    """
    Register autonomous tasks with APScheduler.

    Args:
        scheduler: AsyncIOScheduler instance
        send_fn: Async function to send Telegram messages
    """
    for task_name, task in TASKS.items():
        if not task.get("enabled"):
            continue

        if task["schedule_type"] == "interval":
            scheduler.add_job(
                run_autonomous_task,
                "interval",
                minutes=task["interval_minutes"],
                args=[task_name, send_fn],
                id=task_name,
                max_instances=1,
                replace_existing=True,
            )
            logger.info(f"Registered interval task: {task_name} every {task['interval_minutes']}min")

        elif task["schedule_type"] == "cron":
            scheduler.add_job(
                run_autonomous_task,
                "cron",
                hour=task["hour"],
                minute=task["minute"],
                args=[task_name, send_fn],
                id=task_name,
                max_instances=1,
                replace_existing=True,
            )
            logger.info(f"Registered cron task: {task_name} at {task['hour']:02d}:{task['minute']:02d}")
