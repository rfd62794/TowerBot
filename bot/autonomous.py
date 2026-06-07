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
from infra.prompts import get_prompts_for_task
from infra.db.autonomous import record_agent_action, get_recent_task_actions
from infra.utils import safe_serialize, notify, get_task_type
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

TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def _ralph_scheduled_wrapper(template_name: str, send_fn):
    """
    Push scheduled task to Ralph's queue and run it.
    Ralph handles priority ordering; this wrapper ensures scheduled tasks
    are visible to Ralph's event loop.
    """
    from bot.ralph import ralph, PRIORITY_SCHEDULED

    await ralph.push(PRIORITY_SCHEDULED, {
        "type": "scheduled_task",
        "task_name": template_name
    })
    await run_scheduled_template(template_name, send_fn)


async def system_watchdog(send_fn):
    """
    5-minute system health check — silent unless something is wrong.
    
    Checks:
    - Ollama alive?
    - Budget ok?
    - Queue depth sane?
    """
    issues = []
    
    # Check Ollama health
    try:
        from api.local.ollama_api import ollama_api
        if ollama_api.enabled:
            healthy = ollama_api.health_check()
            if not healthy:
                issues.append("Ollama not healthy")
    except Exception as e:
        logger.debug(f"Ollama check failed: {e}")
    
    # Check budget status
    try:
        from bot.model_manager import can_use_paid_model
        if not can_use_paid_model():
            issues.append("Daily budget cap reached")
    except Exception as e:
        logger.debug(f"Budget check failed: {e}")
    
    # Check queue depth
    try:
        from infra.db.task_queue import get_due_tasks
        due = get_due_tasks()
        if len(due) > 20:
            issues.append(f"Queue depth high: {len(due)} tasks pending")
    except Exception as e:
        logger.debug(f"Queue check failed: {e}")
    
    # Send alert if issues found
    if issues:
        msg = "⚠️ System watchdog alerts:\n" + "\n".join(f"• {i}" for i in issues)
        await send_fn(msg)
        logger.warning(f"System watchdog found issues: {issues}")
    else:
        logger.debug("System watchdog: all checks passed")


async def urgent_email_check(send_fn):
    """
    15-minute urgent email check — anything flagged critical since last check?
    """
    try:
        from tools.communication.gmail import gmail_tools
        
        # Check both accounts for urgent emails
        personal = gmail_tools.get_inbox_summary(account="personal")
        rfd = gmail_tools.get_inbox_summary(account="rfd") if "rfd" in gmail_tools.ACCOUNTS else None
        
        urgent = []
        
        # Check personal for urgent keywords
        for msg in personal.get("recent", []):
            subject = msg.get("subject", "").lower()
            if any(kw in subject for kw in ["urgent", "critical", "asap", "emergency", "deadline"]):
                urgent.append(f"Personal: {msg['from']} — {msg['subject'][:40]}")
        
        # Check RFD for urgent keywords
        if rfd:
            for msg in rfd.get("recent", []):
                subject = msg.get("subject", "").lower()
                if any(kw in subject for kw in ["urgent", "critical", "asap", "emergency", "deadline"]):
                    urgent.append(f"RFD: {msg['from']} — {msg['subject'][:40]}")
        
        if urgent:
            msg = "🚨 Urgent emails detected:\n" + "\n".join(f"• {u}" for u in urgent[:5])
            await send_fn(msg)
            logger.warning(f"Urgent emails found: {len(urgent)}")
        else:
            logger.debug("Urgent email check: no urgent messages")
            
    except Exception as e:
        logger.error(f"Urgent email check failed: {e}")


async def community_opportunity_capture(send_fn):
    """
    Hourly community opportunity capture — find threads worth engaging with.
    """
    try:
        # This would run the community_scout template
        # For now, just log that it ran
        logger.info("Community opportunity capture check")
    except Exception as e:
        logger.error(f"Community opportunity capture failed: {e}")


async def tech_digest(send_fn):
    """
    7:30AM tech digest — summarize recent tech news.
    """
    try:
        # This would run the tech_digest template
        logger.info("Tech digest check")
    except Exception as e:
        logger.error(f"Tech digest failed: {e}")


async def content_decision_prompt(send_fn):
    """
    9:00AM content decision prompt — what to record today.
    """
    try:
        from infra.model_router import route
        from tools.content.videos import get_top_videos
        from tools.games.metrics import get_itch_stats
        
        # Get recent performance data
        top_videos = get_top_videos(days=7, limit=5)
        itch = get_itch_stats()
        
        prompt = f"""Based on this data, suggest what I should record today for YouTube:

Top videos (7d):
{top_videos.get('videos', [])[:3] if top_videos.get('ok') else 'N/A'}

itch.io stats:
{itch.get('games', [])[:2] if itch.get('ok') else 'N/A'}

Suggest 1-2 specific recording ideas that would perform well. Be specific about game and angle."""
        
        result = route(role="reasoning", prompt=prompt)
        if result.get("ok"):
            await send_fn(f"🎬 Content decision for today:\n\n{result.get('result', '')}")
            logger.info("Content decision prompt sent")
    except Exception as e:
        logger.error(f"Content decision prompt failed: {e}")


async def midday_checkin(send_fn):
    """
    1:00PM mid-day check-in — what shipped, what's pending, performance, opportunities.
    """
    try:
        from tools.search.search_tools import get_recent_commits
        from tools.content.videos import get_top_videos
        from infra.db.task_queue import get_due_tasks
        
        # Get data
        commits = get_recent_commits(limit=5)
        top_videos = get_top_videos(days=1, limit=3)
        pending = get_due_tasks()
        
        msg = "🕐 Mid-day check-in:\n\n"
        
        # What shipped
        if commits.get("commits"):
            msg += f"📦 Shipped today: {len(commits['commits'])} commits\n"
            for c in commits['commits'][:2]:
                msg += f"  • {c['message'][:50]}\n"
        
        # What's pending
        if pending:
            msg += f"\n📋 Pending: {len(pending)} tasks\n"
        
        # Top performance
        if top_videos.get("ok") and top_videos.get("videos"):
            msg += f"\n📺 Top today:\n"
            for v in top_videos['videos'][:2]:
                msg += f"  • {v['title'][:40]}: {v['views']} views\n"
        
        await send_fn(msg)
        logger.info("Mid-day check-in sent")
    except Exception as e:
        logger.error(f"Mid-day check-in failed: {e}")


async def evening_content_check(send_fn):
    """
    6:00PM content gap detector + commit digest + VoidDrift delta.
    """
    try:
        from tools.search.search_tools import get_recent_commits
        from tools.games.metrics import get_itch_stats
        from infra.model_router import route
        
        # Get commits today
        commits = get_recent_commits(limit=20)
        today_commits = [c for c in commits.get("commits", []) if _hours_ago(c.get("date", "")) <= 24]
        
        # Get VoidDrift stats
        itch = get_itch_stats()
        voiddrift = None
        if itch.get("ok"):
            for g in itch.get("games", []):
                if "voiddrift" in g.get("title", "").lower():
                    voiddrift = g
                    break
        
        msg = "🌆 Evening content check:\n\n"
        
        # Commits vs content gap
        msg += f"📦 Commits today: {len(today_commits)}\n"
        
        # VoidDrift delta
        if voiddrift:
            msg += f"\n🎮 VoidDrift: {voiddrift.get('views', 0)} views · {voiddrift.get('downloads', 0)} plays\n"
        
        # Commit digest plain English
        if today_commits:
            digest_prompt = f"Summarize these commits in plain English, 2-3 sentences max:\n" + "\n".join(c['message'] for c in today_commits[:5])
            digest = route(role="reasoning", prompt=digest_prompt)
            if digest.get("ok"):
                msg += f"\n📝 Today's work:\n{digest.get('result', '')}"
        
        await send_fn(msg)
        logger.info("Evening content check sent")
    except Exception as e:
        logger.error(f"Evening content check failed: {e}")


async def bedtime_summary(send_fn):
    """
    10:30PM day summary + overnight queue setup.
    """
    try:
        from tools.productivity.google_tasks import list_google_tasks
        from datetime import datetime, timedelta

        # Get tomorrow's tasks
        tasks = list_google_tasks()
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        due_tomorrow = [t for t in tasks.get("tasks", []) if t.get("due_date", "").startswith(tomorrow)]

        msg = "🌙 Bedtime summary:\n\n"

        # What happened today vs morning plan
        msg += "Today's summary: [day completed]\n\n"

        # Tomorrow's overnight queue
        if due_tomorrow:
            msg += f"📋 Overnight queue ({len(due_tomorrow)} tasks):\n"
            for t in due_tomorrow[:3]:
                msg += f"  • {t.get('title', '')}\n"
        else:
            msg += "📋 No tasks queued for overnight\n"

        msg += "\n💤 I'll work on these while you sleep. Good night!"

        await send_fn(msg)
        logger.info("Bedtime summary sent")
    except Exception as e:
        logger.error(f"Bedtime summary failed: {e}")


async def skill_review(send_fn):
    """
    Sunday 6AM self-improvement analysis — analyze last 7 days of agent_actions.
    Proposes improvements, new templates, and drops based on performance patterns.
    """
    try:
        from infra.db.autonomous import get_recent_task_actions
        from infra.model_router import route
        from datetime import datetime, timedelta

        # Get last 7 days of actions
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        actions = get_recent_task_actions(since=seven_days_ago)

        # Build analysis prompt
        prompt = f"""Look at these {len(actions)} agent_actions from the last 7 days:

{actions[:50] if len(actions) > 50 else actions}

Find:
1. Tasks that ran frequently but produced low-quality output (needs better prompts)
2. Ad-hoc research topics that came up 2+ times (should become a template)
3. Notifications that fired but weren't acted on (threshold too low?)
4. Gaps — things Robert asked about that PrivyBot couldn't answer

Propose 1-3 improvements. Format as:
IMPROVE: [task_name] — [what to change and why]
NEW TEMPLATE: [name] — [what it would do and when to run it]
DROP: [task_name] — [why it's not pulling its weight]

Be specific and actionable."""

        result = route(role="reasoning", prompt=prompt)

        if result.get("ok"):
            proposal = result.get("result", "")
            msg = f"🔧 Weekly skill review:\n\n{proposal}\n\nReply APPROVE or REJECT to each proposal."
            await send_fn(msg)
            logger.info("Skill review sent for approval")
        else:
            logger.error(f"Skill review analysis failed: {result.get('error')}")
    except Exception as e:
        logger.error(f"Skill review failed: {e}")


async def _check_and_run_background_task(send_fn):
    """
    Run a random background task from weighted pool every 10 minutes.
    Proactive lightweight work that runs constantly regardless of scheduled tasks.
    """
    try:
        task = _pick_background_task()
        logger.info(f"Running background task: {task[:60]}...")

        # Execute the task using the agent
        result = await respond(task, "background")

        # Log to agent_actions
        record_agent_action(
            task_name="background_task",
            result=safe_serialize(result)[:500],
            duration_ms=0,
            source="background_pool"
        )

        logger.debug(f"Background task completed")
    except Exception as e:
        logger.error(f"Background task failed: {e}")


def _hours_ago(date_str: str) -> int:
    """Calculate hours ago from ISO date string."""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        delta = datetime.now(dt.tzinfo) - dt
        return int(delta.total_seconds() / 3600)
    except:
        return 999


async def budget_status_check(send_fn):
    """
    Hourly budget status check — report if approaching cap.
    """
    try:
        from bot.model_manager import get_budget_status
        status = get_budget_status()

        if status.get("approaching_cap", False):
            msg = f"⚠️ Budget alert: {status.get('quota_used_today', 0):.4f}/{status.get('daily_cap', 0.25)} used"
            await send_fn(msg)
            logger.warning(f"Budget approaching cap: {status}")
        else:
            logger.debug(f"Budget status OK: {status.get('quota_used_today', 0):.4f} used")
    except Exception as e:
        logger.error(f"Budget status check failed: {e}")


async def profile_health_check(send_fn):
    """
    Weekly task: check all browser profiles are still valid.
    Notify immediately if any have expired.
    """
    try:
        from tools.browser.playwright_base import list_profile_status
        status = list_profile_status()
        profiles = status.get("profiles", [])

        if not profiles:
            await send_fn("🔑 No browser profiles set up yet. RDP into Tower and run setup_profile_itch and setup_profile_youtube.")
            return

        expired = [p for p in profiles if not p.get("valid")]
        if expired:
            sites = ", ".join(p["site"] for p in expired)
            await send_fn(
                f"⚠️ Browser profiles expired: {sites}\n"
                f"RDP into Tower and run: run_named_command('setup_profile_{expired[0]['site']}')",
                urgent=True
            )
        else:
            logger.info(f"[profiles] all {len(profiles)} profiles valid")

    except Exception as e:
        logger.warning(f"[profile_health_check] failed: {e}")


async def request_approval(
    action_type: str,
    summary: str,
    payload: dict,
    timeout_minutes: int = 30
) -> bool:
    """
    Send approval request to Telegram. Waits for YES/NO reply.
    Returns True if approval created successfully, False otherwise.
    Maximum one pending approval at a time.
    """
    from infra.db.approvals import create_approval, get_latest_pending

    # Check for existing pending approval
    existing = get_latest_pending()
    if existing:
        logger.warning(f"[approval] skipped: pending approval already exists (ID: {existing['id']})")
        return False

    approval_id = create_approval(action_type, summary, payload, timeout_minutes)
    if not approval_id:
        logger.warning(f"[approval] failed to create approval record for {action_type}")
        return False

    message = (
        f"🔔 *Action requested:* {action_type}\n"
        f"{summary}\n\n"
        f"Reply *YES* to execute, *NO* to skip\n"
        f"_(expires in {timeout_minutes} min — ID: {approval_id})_"
    )

    await notify(message, send_fn)
    logger.info(f"[approval] requested: {action_type} (ID: {approval_id})")
    return True

# Weighted background task pools — proactive lightweight work that runs constantly
# 60% Core, 30% Adjacent, 10% Expanding
# These run every 10 minutes regardless of scheduled tasks.
# Very lightweight: 1-2 tool calls, no heavy inference. Silent if nothing actionable.

BACKGROUND_TASKS_CORE = [
    # Rust / Bevy / Game Dev (weight: high)
    "Search HackerNews for Rust game development posts with >30 points today. Check content_seen. Surface if new and relevant to VoidDrift.",
    "Find one new crates.io release relevant to game development or ECS. Check if it could benefit VoidDrift. Mark seen.",
    "Search r/bevy for questions or showcases posted in the last 6 hours. Surface anything relevant to Robert's Bevy 0.15 work.",
    "Search r/rust for posts about game development, ECS patterns, or WASM that Robert hasn't seen. Check content_seen first.",
    "Search HN for 'Bevy' or 'Rust game' posts. Surface any with >20 points not already seen.",
    "Check r/incremental_games for new posts about idle game design, mechanics, or launches. Mark seen.",
    "Search for new VoidDrift or openagent-directive mentions on the web. Notify immediately if found.",
    "Check PyPI for openagent-directive download trend. Note if direction changed from yesterday.",
    "Search HN for Python automation or CLI tooling posts with >40 points. Relevant to OpenAgent direction.",
    "Find one itch.io game in the idle/incremental category launched this week. Note what mechanic it leads with.",
]

BACKGROUND_TASKS_ADJACENT = [
    # Game Design / Indie Dev / Content / AI
    "Find one post-mortem or launch retrospective from an indie game developer on r/gamedev or HN. Summarize the key lesson in one sentence.",
    "Search for a game design pattern or mechanic discussion on r/gamedev with >50 upvotes this week. Note if applicable to VoidDrift.",
    "Find a YouTube Shorts creator in gaming who gained >1000 subscribers this week. Check content_seen. Note what's working for them.",
    "Search HN for AI agent architecture, autonomous systems, or LLM tool-use posts with >50 points. Relevant to PrivyBot direction.",
    "Find one interesting Python automation or workflow tool posted on HN or Reddit this week. Check if it should become a PrivyBot tool.",
    "Search r/selfhosted for self-hosted tools relevant to Robert's stack (Telegram bots, local LLMs, home servers). Mark seen.",
    "Find one content creator in the indie dev space who posted a video about their tools or workflow. Note what they use.",
    "Search for Rust vs other languages performance discussions with interesting benchmarks. Note anything applicable to VoidDrift.",
    "Find an AI assistant or agent project on HN that does something PrivyBot doesn't do yet. Note the capability gap.",
    "Search for 'solopreneur' or 'indie hacker' posts about passive income from games or tools with >30 points.",
]

BACKGROUND_TASKS_EXPANDING = [
    # Wider intellectual territory — unexpected connections
    "Find a random Wikipedia article in systems thinking, complexity theory, or emergence. Summarize the core idea in 2 sentences.",
    "Search HN for 'Ask HN' posts about learning, building, or shipping with >100 points. Surface the most interesting response.",
    "Find a post about behavioral economics or decision theory on HN or r/psychology. Note any connection to game design.",
    "Search for a paper abstract on arxiv in human-computer interaction or game theory. Summarize if accessible.",
    "Find one historical example of a technology or idea that was ahead of its time. Note the parallel to something Robert is building.",
    "Search for a post about cognitive science, memory, or learning systems with >40 points on HN. Note anything applicable to content creation.",
    "Find one post about visual design, typography, or color theory on HN or Dribbble. Note if applicable to VoidDrift UI.",
    "Search for an unusual use of automation or AI in a creative domain (music, art, writing). Note the technique.",
    "Find a post about the philosophy of tools, craftmanship, or expertise with >50 HN points. Surface if insightful.",
    "Search wiki_random() for a random article. If the topic connects to any of Robert's projects in an unexpected way, note the connection.",
]


def _pick_background_task() -> str:
    """Pick a random task weighted by category: 60% core, 30% adjacent, 10% expanding."""
    import random
    roll = random.random()
    if roll < 0.60:
        return random.choice(BACKGROUND_TASKS_CORE)
    elif roll < 0.90:
        return random.choice(BACKGROUND_TASKS_ADJACENT)
    else:
        return random.choice(BACKGROUND_TASKS_EXPANDING)

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
    
    # Inject base prompts based on task type
    try:
        task_type = _get_task_type(task_name)
        context = get_prompts_for_task(task_type)
        if context:
            full_prompt = f"{context}\n\n---\n\n{prefix}{task['persona']}\n\n{task['prompt']}"
        else:
            full_prompt = f"{prefix}{task['persona']}\n\n{task['prompt']}"
    except Exception as e:
        logger.warning(f"[autonomous] failed to inject prompts for {task_name}: {e}")
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

        record_agent_action(task_name, safe_serialize(result), duration_ms, urgent)
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
                    record_agent_action("fallback", safe_serialize(fallback_result))
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
                result=safe_serialize(result),
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
        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        tasks_today = [t for t in all_tasks if t.get("due_date") == today and t.get("status") != "completed"]
        upcoming_tasks = [t for t in all_tasks if t.get("due_date") and t.get("due_date") >= today and t.get("due_date") <= tomorrow and t.get("status") != "completed"]

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
        record_agent_action("comment_new_videos", safe_serialize(result_msg), duration_ms, 0)

        if comments_posted > 0:
            await send_fn(f"💬 Posted {comments_posted} comments on new videos")

    except Exception as e:
        logger.error(f"comment_new_videos task failed: {e}")
        record_agent_action("comment_new_videos", safe_serialize(f"ERROR: {str(e)}"), 0, 0)


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
        if result is None or not isinstance(result, dict):
            logger.warning(f"[{template_name}] runner returned non-dict: {type(result)}")
            return
        logger.info(f"Chain {chain_id} completed: {result.get('status', 'unknown')}")

        # Log to agent_actions for unified history
        record_agent_action(
            task_name=template_name,
            result=safe_serialize(result),
            duration_ms=0,
            source="template"
        )

        # Notification triggers
        if template_name == "community_scout":
            upvotes = result.get("upvotes", 0) if isinstance(result, dict) else 0
            if upvotes >= 20:
                title = result.get("title", "New thread")
                url = result.get("url", "")
                subreddit = result.get("subreddit", "unknown")
                await request_approval(
                    action_type="community_reply",
                    summary=(
                        f"r/{subreddit} — {title}\n"
                        f"{upvotes} upvotes\n"
                        f"Draft reply: mention VoidDrift as relevant to '{title}'\n"
                        f"Link: {url}"
                    ),
                    payload={"url": url, "title": title, "subreddit": subreddit}
                )
        elif template_name == "blog_scaffold":
            draft_title = result.get("title", "New draft") if isinstance(result, dict) else "New draft"
            await notify(f"📝 Blog draft ready: {draft_title} — review and edit before publishing", send_fn)

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
                    _ralph_scheduled_wrapper,
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
                    _ralph_scheduled_wrapper,
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
                await notify(f"💭 {result.get('summary', task_prompt[:80])}", send_fn)
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

    # Register 5-minute system watchdog
    scheduler.add_job(
        system_watchdog,
        "interval",
        minutes=5,
        id="system_watchdog",
        max_instances=1,
        args=[send_fn]
    )
    logger.info("Registered system watchdog: every 5 minutes")

    # Register 15-minute urgent email check
    scheduler.add_job(
        urgent_email_check,
        "interval",
        minutes=15,
        id="urgent_email_check",
        max_instances=1,
        args=[send_fn]
    )
    logger.info("Registered urgent email check: every 15 minutes")

    # Register idle detection job (runs every 15 minutes)
    scheduler.add_job(
        _check_and_run_idle_task,
        "interval",
        minutes=15,
        id="idle_task_checker"
    )
    logger.info("Registered idle detection job: _check_and_run_idle_task every 15min")

    # Register 25-minute background task pool
    scheduler.add_job(
        _check_and_run_background_task,
        "interval",
        minutes=25,
        id="background_task_checker",
        max_instances=1,
        args=[send_fn]
    )
    logger.info("Registered background task pool: every 25 minutes")

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

    # Register hourly community opportunity capture
    scheduler.add_job(
        community_opportunity_capture,
        "interval",
        hours=1,
        id="community_opportunity_capture",
        max_instances=1,
        args=[send_fn]
    )
    logger.info("Registered community opportunity capture: every hour")

    # Register hourly budget status check
    scheduler.add_job(
        budget_status_check,
        "interval",
        hours=1,
        id="budget_status_check",
        max_instances=1,
        args=[send_fn]
    )
    logger.info("Registered budget status check: every hour")

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

    # Register 7:30AM tech digest
    scheduler.add_job(
        tech_digest,
        "cron",
        hour=7,
        minute=30,
        id='tech_digest',
        max_instances=1,
        args=[send_fn],
        replace_existing=True
    )
    logger.info("Registered tech_digest: daily 07:30")

    # Register 9:00AM content decision prompt
    scheduler.add_job(
        content_decision_prompt,
        "cron",
        hour=9,
        minute=0,
        id='content_decision_prompt',
        max_instances=1,
        args=[send_fn],
        replace_existing=True
    )
    logger.info("Registered content_decision_prompt: daily 09:00")

    # Register 10:00AM debt followup (Mon/Wed/Fri)
    scheduler.add_job(
        comment_new_videos,
        "cron",
        hour=10,
        minute=0,
        day_of_week='mon,wed,fri',
        id='debt_followup',
        max_instances=1,
        args=[send_fn],
        replace_existing=True
    )
    logger.info("Registered debt_followup: Mon/Wed/Fri 10:00")

    # Register 10:00AM comment_new_videos job
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

    # Register 1:00PM mid-day check-in
    scheduler.add_job(
        midday_checkin,
        "cron",
        hour=13,
        minute=0,
        id='midday_checkin',
        max_instances=1,
        args=[send_fn],
        replace_existing=True
    )
    logger.info("Registered midday_checkin: daily 13:00")

    # Register 6:00PM evening content check
    scheduler.add_job(
        evening_content_check,
        "cron",
        hour=18,
        minute=0,
        id='evening_content_check',
        max_instances=1,
        args=[send_fn],
        replace_existing=True
    )
    logger.info("Registered evening_content_check: daily 18:00")

    # Register 10:30PM bedtime summary
    scheduler.add_job(
        bedtime_summary,
        "cron",
        hour=22,
        minute=30,
        id='bedtime_summary',
        max_instances=1,
        args=[send_fn],
        replace_existing=True
    )
    logger.info("Registered bedtime_summary: daily 22:30")

    # Register Sunday 6AM skill review
    scheduler.add_job(
        skill_review,
        "cron",
        day_of_week='sun',
        hour=6,
        minute=0,
        id='skill_review',
        max_instances=1,
        args=[send_fn],
        replace_existing=True
    )
    logger.info("Registered skill_review: Sunday 06:00")
