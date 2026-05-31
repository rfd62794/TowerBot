"""Autonomous task runner — scheduled agent execution without user presence."""

import time
import logging
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.agent import respond
from infra.db.autonomous import record_agent_action, get_recent_task_actions

logger = logging.getLogger("privy.autonomous")

# Fallback micro-tasks for when primary tasks find nothing
FALLBACK_TASKS = [
    # Post builder — runs as primary fallback, advances one stage
    (
        "Check memories for post pipeline state: look for any memory starting "
        "with 'Q1 ready:', 'Research:', 'Skeleton:', or 'Draft:'. "
        "Find the most advanced post in progress. "
        "\n\n"
        "If NO post in progress: "
        "Pick the highest-resonance topic from content_pipeline_inventory memory. "
        "Generate the Q1 prompt — the specific scene question Robert needs to answer. "
        "Save as memory 'Q1 ready: [topic]'. Stop here. "
        "\n\n"
        "If Q1 ready but NO research: "
        "Search for context about the topic: use get_recent_commits, get_itch_stats, "
        "search_local_code for related code patterns, web_search if relevant. "
        "Gather 3-5 concrete facts that would help Robert answer the questions. "
        "Save as memory 'Research: [topic] — [key findings in 2-3 sentences]'. Stop. "
        "\n\n"
        "If research done but NO skeleton: "
        "Build a WordPress post skeleton with 5 labeled sections "
        "(MOMENT, SURPRISE, STRUGGLE, LESSON, NEXT). "
        "For each section: write the specific prompt question Robert needs to answer "
        "AND include the relevant research context beneath it. "
        "Save as memory 'Skeleton: [topic]'. Stop. "
        "\n\n"
        "If skeleton done but NO WordPress draft: "
        "Read the skeleton from memory. Call create_blog_draft() with the full "
        "skeleton content as a formatted WordPress post. "
        "Save as memory 'Draft: [topic] — post_id: [N] — edit: [URL]'. "
        "Mark this result URGENT. Stop. "
        "\n\n"
        "RULE: Advance exactly ONE stage per run. Never skip stages. "
        "Always stop after completing the current stage."
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
    "self_expansion_planner": {
        "schedule_type": "cron",
        "hour": 7,
        "minute": 0,
        "enabled": True,
        "prompt": (
            "Call read_current_state() to get current system state. "
            "Call find_opportunities(focus='next phase') to identify top priority. "
            "Call elaborate_task() on the top opportunity description. "
            "Call generate_directive() to create the RFD directive template. "
            "Fill in the directive template with specific implementation details. "
            "Save completed directive as memory 'Proposed directive: [name]'. "
            "Mark URGENT so Robert sees it in morning briefing."
        ),
    },
    "blog_structure_generator": {
        "schedule_type": "cron",
        "hour": 1,
        "minute": 0,
        "day_of_week": 6,  # Sunday
        "enabled": True,
        "prompt": (
            "Check memory for 'Blog humanization status' — are all 4 existing posts humanized? "
            "If not: identify which post is next, call get_blog_post() to pull current content, "
            "apply five-question extraction frame, draft opening rewrite. "
            "Call update_blog_post() to save the rewrite. "
            "Save as memory 'Blog rewrite ready: [post name]'. "
            "If all 4 are humanized: check recent commits and YouTube performance, "
            "pick the highest-resonance topic from the 70-post inventory, "
            "generate five-question extraction skeleton using RFD Content Frame "
            "(MOMENT → SURPRISE → STRUGGLE → LESSON → NEXT). "
            "Call create_blog_draft() to create WordPress draft. "
            "Save as memory 'Blog draft created: [topic]'. "
            "Mark URGENT."
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

        # Fallback: consecutive empty runs trigger a micro-task
        nothing_phrases = [
            "0 mentions", "0 found", "nothing important",
            "no urgent", "no changes detected", "nothing new"
        ]
        if any(p in result.lower() for p in nothing_phrases):
            # Count recent empty runs for this task (last 8 hours)
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
                    thread_id="autonomous_fallback"
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
            job_kwargs = {
                "hour": task["hour"],
                "minute": task["minute"],
                "args": [task_name, send_fn],
                "id": task_name,
                "max_instances": 1,
                "replace_existing": True,
            }
            if "day_of_week" in task:
                job_kwargs["day_of_week"] = task["day_of_week"]
            scheduler.add_job(
                run_autonomous_task,
                "cron",
                **job_kwargs
            )
            day_str = f" day {task['day_of_week']}" if "day_of_week" in task else ""
            logger.info(f"Registered cron task: {task_name} at {task['hour']:02d}:{task['minute']:02d}{day_str}")
