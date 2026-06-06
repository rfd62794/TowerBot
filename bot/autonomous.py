"""Autonomous task runner — scheduled agent execution without user presence."""

import os
import time
import logging
import random
import psutil
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.agent import respond
from bot.task_runner import resolve_task, get_all_resolved_tasks, get_task_model_role
from infra.model_router import route
from infra.db.autonomous import record_agent_action, get_recent_task_actions
from infra.db.system_metrics import record_system_snapshot
from infra.db.bot_state import get_dev_mode
from infra.db.task_queue import get_due_tasks, mark_running, mark_complete, mark_failed
from scripts.update import check_for_updates
from infra.chain.observer import observe_completed_chains
from infra.memory_manager import memory_manager
from infra.chain.template_loader import list_templates, load_template
from infra.chain.runner import ChainRunner
from infra.db.chains import create_chain

logger = logging.getLogger("privy.autonomous")

# Idle task pool — fallback tasks when no autonomous work is queued
IDLE_TASKS = [
    # Research
    "Search HackerNews for Rust ECS or game development posts with >30 points. Summarize the most relevant one to VoidDrift development in 2 sentences. If already served, skip it.",
    "Search r/bevy for questions posted in the last 24 hours that Robert could answer based on VoidDrift experience. Surface the most relevant one.",
    "Search itch.io or r/incremental_games for new idle game launches this week. Find one that's doing well and note what mechanic is driving it.",
    "Search HackerNews for 'Python CLI' or 'Python automation' with >20 points today. Summarize anything relevant to OpenAgent.",
    "Search r/rust for posts about game development or ECS patterns posted today. Surface the most interesting one.",

    # Content ideas
    "Generate 3 YouTube Short title concepts for Everything is Crab using the identity transformation pattern (what the game turned you into). Make each title specific and visceral — not generic.",
    "Generate 3 YouTube Short title concepts for Dune: Awakening using survival or discovery moments. Each title should create a question in the viewer's mind.",
    "Look at recent VoidDrift commits using get_recent_commits(). Generate 2 Short title concepts that turn the most recent technical change into a player-facing story.",
    "Find a trending game mechanic discussion on Reddit or HN. Explain in 2 sentences how it relates to VoidDrift's current design.",

    # Monitoring
    "Search the web for 'VoidDrift game' or 'VoidDrift Bevy' using web_search(). Report any new mentions not previously seen.",
    "Search the web for 'openagent-directive' or 'OpenAgent CLI'. Report any new mentions, blog posts, or GitHub forks.",
    "Use get_pypi_stats() to check OpenAgent download counts. Compare to last known baseline and note the trend.",
    "Search r/incremental_games for threads where VoidDrift could be recommended. Check content_seen before surfacing.",
    "Use get_itch_stats() and check if VoidDrift views or plays changed in the last few hours.",

    # Drafts
    "Using get_recent_commits(), draft a 2-sentence LinkedIn post about the most recent VoidDrift or PrivyBot commit. Keep it technical but accessible.",
    "Draft a 3-point outline for a blog post using the most interesting commit from the last 7 days as the hook. Use the RFD Content Frame: MOMENT → SURPRISE → STRUGGLE → LESSON → NEXT.",
    "Review the last 3 YouTube Shorts titles published using get_top_videos(). Suggest 2 improved versions using the identity transformation pattern.",

    # Intelligence
    "Search HN for 'indie game' with >50 points today. Find the top result and summarize what's driving its success in one sentence.",
    "Search r/gamedev for posts about monetization, launch strategy, or wishlist building with >30 upvotes. Surface the most relevant to VoidDrift's Android launch.",

    # Utility
    "Use list_google_tasks() to find the oldest overdue task. Draft a one-paragraph completion plan for it.",
]


async def _notify(message: str, send_fn, urgent: bool = False) -> None:
    """Send immediate Telegram notification from autonomous task."""
    try:
        prefix = "🔴 " if urgent else "💡 "
        await send_fn(f"{prefix}{message}")
    except Exception as e:
        logger.warning(f"[autonomous] notification failed: {e}")


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
        # Check if task has a model_role for routing
        model_role = get_task_model_role(task_name)
        
        if model_role:
            # Use model_router for tasks with defined model_role
            logger.info(f"[autonomous] task {task_name} using model_router with role: {model_role}")
            routed = route(
                role=model_role,
                prompt=full_prompt
            )
            result = routed["result"]
        else:
            # Fall back to agent.respond() for tasks without model_role
            logger.info(f"[autonomous] task {task_name} using agent.respond() (no model_role)")
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


async def self_direction_loop(send_fn):
    """
    Daily self-direction loop — Tower reads its state and queues its own tasks.

    Runs at 07:00 daily. Reads current state, uses reasoning model to prioritize
    3 highest-value tasks, queues them, and saves the plan as memory.

    Args:
        send_fn: Async function to send Telegram messages
    """
    try:
        from tools.repo.directive import read_current_state
        from tools.productivity.google_tasks import list_google_tasks
        from tools.productivity.goals import get_upcoming_tasks
        from tools.communication.gmail import gmail_tools
        from tools.games.metrics import _games
        from tools.meta.delegation import delegation_tools

        logger.info("Starting self-direction loop")

        # Read current state
        state = read_current_state()
        if not state.get("ok"):
            logger.error(f"Failed to read current state: {state.get('error')}")
            return

        # Read tasks
        all_tasks = list_google_tasks()
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        tasks_today = [t for t in all_tasks if t.get("due_date") == today and t.get("status") != "completed"]
        upcoming_tasks = get_upcoming_tasks(hours=24)

        # Check for Research: tasks and run research_request template
        research_tasks = [t for t in all_tasks if t.get("title", "").startswith("Research:") and t.get("status") != "completed"]
        for research_task in research_tasks:
            try:
                topic = research_task["title"].replace("Research:", "").strip()
                logger.info(f"Running research_request for topic: {topic}")
                
                # Load template and create chain
                from infra.chain.template_loader import load_template
                template = load_template("research_request")
                
                # Substitute topic in template steps
                from infra.chain.runner import ChainRunner
                from infra.model_router import route
                
                chain_id = create_chain(template_name="research_request")
                
                # Replace {topic} placeholder in template steps
                steps_with_topic = []
                for step in template["steps"]:
                    step_copy = step.copy()
                    step_copy["config"] = step["config"].copy()
                    for key, value in step_copy["config"].items():
                        if isinstance(value, str):
                            step_copy["config"][key] = value.replace("{topic}", topic)
                    steps_with_topic.append(step_copy)
                
                # Run the chain
                runner = ChainRunner(
                    tool_registry=TOOL_REGISTRY,
                    call_model_fn=lambda prompt, role="reasoning": route(role=role, prompt=prompt)["result"],
                    create_chain_fn=create_chain
                )
                result = runner.run(chain_id, steps_with_topic)
                
                # Extract summary from final payload
                summary = ""
                if result.get("status") == "complete":
                    from infra.db.payloads import get_payload
                    final_step = result.get("current_step", 0) - 1
                    # Get the final step's output payload
                    # For now, just notify completion
                    summary = f"Research completed for: {topic}"
                
                await send_fn(f"🔬 Research complete: {topic}\n\n{summary}")
                
                # Mark task as completed
                from tools.productivity.google_tasks import complete_google_task
                complete_google_task(research_task["id"])
                logger.info(f"Marked research task as completed: {research_task['id']}")
            except Exception as e:
                logger.error(f"Research task failed: {e}")

        # Read inbox summary
        inbox_result = gmail_tools.get_inbox_summary(account="personal")

        # Read itch stats
        itch_result = _games.get_itch_stats()

        # Read blog posts
        from tools.communication.blog import blog_tools
        blog_result = blog_tools.get_blog_posts(status="draft")

        # Build state summary for reasoning model
        state_summary = f"""
CURRENT STATE (Phase {state.get('current_phase', 'Unknown')}):
- Test floor: {state.get('test_floor', {}).get('passing', 0)}/{state.get('test_floor', {}).get('required', 0)}
- What is built: {', '.join(state.get('what_is_built', [])[:3])}
- What is next: {', '.join(state.get('what_is_next', [])[:3])}
- Recent commits: {len(state.get('recent_commits', []))}

TASKS:
- Tasks due today: {tasks_today.get('count', 0)}
- Upcoming tasks (24h): {upcoming_tasks.get('count', 0)}

INBOX:
- Unread count: {inbox_result.get('unread_count', 0)}

ITCH.IO:
- Games: {itch_result.get('count', 0)}

BLOG:
- Draft posts: {len(blog_result.get('posts', [])) if blog_result.get('ok') else 0}
"""

        # Use reasoning model to decide on 3 highest-value tasks
        reasoning_prompt = f"""
You are Tower, an autonomous agent. Review the current state below and identify the 3 highest-value tasks to queue for today.

{state_summary}

Respond with exactly 3 task descriptions, one per line. Each task should:
- Be actionable and specific
- Align with current phase priorities
- Be achievable with available tools
- Not require user input

Format your response as:
1. [Task description]
2. [Task description]
3. [Task description]
"""

        routed = route(role="reasoning", prompt=reasoning_prompt)
        result = routed["result"]
        logger.info(f"Reasoning model suggested: {result[:200]}")

        # Parse the 3 tasks
        task_lines = [line.strip() for line in result.split('\n') if line.strip() and line[0].isdigit()]
        tasks_to_queue = task_lines[:3]

        # Queue each task
        queued_count = 0
        for task_desc in tasks_to_queue:
            try:
                # Extract task description (remove number prefix)
                clean_desc = task_desc.split('.', 1)[1].strip() if '.' in task_desc else task_desc
                queue_result = delegation_tools.queue_task(
                    prompt=clean_desc,
                    task_name="self_direction",
                    priority="normal",
                    run_immediately=True
                )
                if queue_result.get("ok"):
                    queued_count += 1
                    logger.info(f"Queued task: {clean_desc[:50]}")
                else:
                    logger.warning(f"Failed to queue task: {queue_result.get('error')}")
            except Exception as e:
                logger.error(f"Error queuing task: {e}")

        # Save plan as memory
        date_str = datetime.now().strftime("%Y-%m-%d")
        plan_content = f"""
Self-direction plan for {date_str}:
- Tasks queued: {queued_count}/3
- Tasks:
{chr(10).join(f'  - {t}' for t in tasks_to_queue)}
- Reasoning model used: {routed.get('model_used', 'unknown')}
- Reasoning result: {result}
"""
        memory_key = f"autonomous_plan_{date_str}"
        memory_manager.save(memory_key, plan_content, layer="project")
        logger.info(f"Saved plan to memory: {memory_key}")

        # Send notification
        await send_fn(f"🤖 Self-direction complete: {queued_count} tasks queued for {date_str}")

    except Exception as e:
        logger.error(f"Self-direction loop failed: {e}")
        await send_fn(f"❌ Self-direction failed: {str(e)}")


async def comment_new_videos(send_fn):
    """
    Daily task: find videos published in last 25 hours, post template comment if none exists.
    """
    try:
        from tools.content.videos import get_top_videos, post_video_comment
        import yaml

        logger.info("Starting comment_new_videos task")

        # Load comment templates
        template_path = "config/comment_templates.yaml"
        try:
            with open(template_path, "r") as f:
                templates = yaml.safe_load(f)
            series_keys = list(templates.get("series", {}).keys())
        except Exception as e:
            logger.error(f"Failed to load comment templates: {e}")
            return

        # Get videos published in last 25 hours
        videos_result = get_top_videos(days=2, limit=50)  # Get more to filter by time
        if not videos_result.get("ok"):
            logger.error(f"Failed to get videos: {videos_result.get('error')}")
            return

        videos = videos_result.get("videos", [])
        now = datetime.now()
        cutoff = now - timedelta(hours=25)

        # Filter videos published in last 25 hours
        recent_videos = []
        for video in videos:
            try:
                pub_date = datetime.fromisoformat(video["published_at"].replace("Z", "+00:00"))
                if pub_date >= cutoff:
                    recent_videos.append(video)
            except Exception:
                continue

        # Limit to 10 comments per run
        recent_videos = recent_videos[:10]

        if not recent_videos:
            logger.info("No videos published in last 25 hours")
            return

        logger.info(f"Found {len(recent_videos)} videos in last 25 hours")

        # For each video, post comment (TODO: check if comment already exists)
        comments_posted = 0
        for video in recent_videos:
            video_id = video["video_id"]
            title = video["title"]

            # Determine series from title
            series = None
            for key in series_keys:
                if key.lower() in title.lower():
                    series = key
                    break

            # Post comment
            result = post_video_comment(video_id=video_id, series=series)

            if result.get("ok"):
                comments_posted += 1
                logger.info(f"Posted comment on {video_id} (series: {series or 'default'})")
            else:
                error_code = result.get("code", "unknown")
                if error_code == "scope_missing":
                    logger.warning("OAuth scope missing - stopping task")
                    await send_fn("⚠️ YouTube comment scope missing - task stopped")
                    return
                logger.error(f"Failed to post comment on {video_id}: {result.get('error')}")

        # Log result to agent_actions
        duration_ms = 0  # Not tracking duration for this task
        result_msg = f"Posted {comments_posted}/{len(recent_videos)} comments"
        record_agent_action("comment_new_videos", result_msg, duration_ms, 0)

        if comments_posted > 0:
            await send_fn(f"💬 Posted {comments_posted} comments on new videos")

    except Exception as e:
        logger.error(f"comment_new_videos task failed: {e}")
        record_agent_action("comment_new_videos", f"ERROR: {str(e)}", 0, 0)


async def run_scheduled_template(template_name: str, send_fn):
    """
    Execute a template triggered by scheduler.

    Loads template, creates chain, runs via ChainRunner.
    Sends result via Telegram if template has send_result flag.

    Args:
        template_name: Template name from templates/
        send_fn: Async function to send Telegram messages
    """
    try:
        logger.info(f"Running scheduled template: {template_name}")

        # Load template
        template = load_template(template_name)
        trigger = template.get("trigger", {})

        # Check stop_after_hour if present
        if trigger.get("stop_after_hour"):
            current_hour = datetime.now().hour
            if current_hour >= trigger["stop_after_hour"]:
                logger.info(f"Template {template_name} stopped (after {trigger['stop_after_hour']}:00)")
                return

        # Create chain
        chain_id = create_chain(template_name=template_name)
        logger.info(f"Created chain {chain_id} for template {template_name}")

        # Run chain via ChainRunner
        # Note: Need to inject tool_registry and call_model_fn
        # For now, use minimal runner with no-op dependencies
        from tools.registry import TOOL_REGISTRY
        from infra.model_router import route as model_route

        def call_model_fn(role: str, prompt: str) -> str:
            routed = model_route(role=role, prompt=prompt)
            return routed.get("result", "")

        runner = ChainRunner(
            tool_registry=TOOL_REGISTRY,
            call_model_fn=call_model_fn,
            create_chain_fn=create_chain
        )

        result = runner.run(chain_id, template["steps"])
        logger.info(f"Chain {chain_id} completed: {result.get('status', 'unknown')}")

        # Log to agent_actions for unified history
        import json
        record_agent_action(
            task_name=template_name,
            result=json.dumps(result),
            duration_ms=0,
            source="template"
        )

        # Notification triggers
        if template_name == "community_scout":
            upvotes = result.get("upvotes", 0) if isinstance(result, dict) else 0
            if upvotes >= 20:
                title = result.get("title", "New thread")
                url = result.get("url", "")
                await _notify(f"Community opportunity: {title} ({upvotes} upvotes) — {url}", send_fn)
        elif template_name == "blog_scaffold":
            draft_title = result.get("title", "New draft") if isinstance(result, dict) else "New draft"
            await _notify(f"📝 Blog draft ready: {draft_title} — review and edit before publishing", send_fn)

        # Send result if template has send_result flag
        if template.get("send_result", False):
            await send_fn(f"📋 {template_name}:\n{result.get('message', 'Complete')}")

    except Exception as e:
        logger.error(f"Scheduled template {template_name} failed: {e}")
        await send_fn(f"❌ Template {template_name} failed: {str(e)}")


def setup_template_scheduler(scheduler: AsyncIOScheduler, send_fn):
    """
    Register template-based scheduled jobs with APScheduler.

    Scans templates/ for trigger.schedule configs and registers jobs.
    Supports interval (minutes) and cron (hour, minute, day_of_week) triggers.

    Args:
        scheduler: AsyncIOScheduler instance
        send_fn: Async function to send Telegram messages
    """
    templates = list_templates(source="all")
    scheduled_count = 0

    for template_info in templates:
        template_name = template_info["name"]
        try:
            template = load_template(template_name)
            trigger = template.get("trigger", {})

            if trigger.get("type") != "schedule":
                continue

            job_id = f"template_{template_name}"

            if "interval_minutes" in trigger:
                # Interval schedule
                scheduler.add_job(
                    run_scheduled_template,
                    "interval",
                    minutes=trigger["interval_minutes"],
                    args=[template_name, send_fn],
                    id=job_id,
                    max_instances=1,
                    replace_existing=True
                )
                logger.info(f"Registered template schedule: {template_name} every {trigger['interval_minutes']}min")
                scheduled_count += 1

            elif "hour" in trigger and "minute" in trigger:
                # Cron schedule
                job_kwargs = {
                    "hour": trigger["hour"],
                    "minute": trigger["minute"],
                    "args": [template_name, send_fn],
                    "id": job_id,
                    "max_instances": 1,
                    "replace_existing": True
                }
                if "day_of_week" in trigger:
                    job_kwargs["day_of_week"] = trigger["day_of_week"]

                scheduler.add_job(
                    run_scheduled_template,
                    "cron",
                    **job_kwargs
                )
                day_str = f" day {trigger['day_of_week']}" if 'day_of_week' in trigger else ""
                logger.info(f"Registered template schedule: {template_name} at {trigger['hour']:02d}:{trigger['minute']:02d}{day_str}")
                scheduled_count += 1

        except Exception as e:
            logger.warning(f"Failed to register template schedule for {template_name}: {e}")

    logger.info(f"Template scheduler registered {scheduled_count} jobs")


IDLE_THRESHOLD_MINUTES = 15


async def _check_and_run_idle_task() -> None:
    """If no task ran in the last 15 minutes, pick a random idle task and run it."""
    try:
        from infra.db.autonomous import get_overnight_actions
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(minutes=IDLE_THRESHOLD_MINUTES)
        recent = [a for a in get_overnight_actions()
                  if a.get("ran_at", "") >= cutoff.isoformat()]

        if recent:
            return  # something ran recently, stay quiet

        task_prompt = random.choice(IDLE_TASKS)
        logger.info(f"[idle] No task in {IDLE_THRESHOLD_MINUTES}m — running idle task")

        try:
            result = await run_template_task("idle_task", prompt_override=task_prompt)
            if result and result.get("ok"):
                await _notify(f"💭 {result.get('summary', task_prompt[:80])}")
        except Exception as e:
            logger.warning(f"[idle] task failed: {e}")
    except Exception as e:
        logger.warning(f"[idle] checker failed: {e}")


def setup_autonomous_scheduler(scheduler: AsyncIOScheduler, send_fn):
    """
    Register autonomous tasks with APScheduler.

    Args:
        scheduler: AsyncIOScheduler instance
        send_fn: Async function to send Telegram messages
    """
    # Register template-based scheduled jobs first
    setup_template_scheduler(scheduler, send_fn)

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

    # Register idle detection job (runs every 15 minutes)
    scheduler.add_job(
        _check_and_run_idle_task,
        "interval",
        minutes=15,
        id="idle_task_checker"
    )
    logger.info("Registered idle detection job: _check_and_run_idle_task every 15min")

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

    # Register self-direction loop job
    scheduler.add_job(
        self_direction_loop,
        "interval",
        minutes=30,
        id='self_direction',
        max_instances=1,
        args=[send_fn],
        replace_existing=True
    )
    logger.info("Registered self-direction loop: every 30 minutes")

    # Register comment_new_videos job
    scheduler.add_job(
        comment_new_videos,
        "cron",
        hour=10,
        minute=0,
        id='comment_new_videos',
        max_instances=1,
        args=[send_fn],
        replace_existing=True
    )
    logger.info("Registered comment_new_videos: daily 10:00")
