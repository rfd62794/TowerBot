"""Scheduler — background tasks for periodic operations."""

import asyncio
import logging
import subprocess
import pytz
from datetime import datetime, timedelta

from tools.content.channel import get_channel_summary, get_channel_summary_range
from tools.productivity.calendar import get_today_schedule
from api.google.calendar_api import get_events_soon
from tools.communication.gmail import get_all_inbox_summary
from infra.polling import polling_manager

from infra.db import (
    record_channel_day, get_game_history, get_scheduled_videos,
    queue_observation, get_pending_observations, mark_sent, flush_morning_queue,
    get_upcoming_scheduled, get_tasks_due_today, get_current_weekly_plan,
    get_channel_history, get_tasks,
    get_last_stable_commit, get_last_deploy, record_deploy, mark_verify_passed, mark_stable,
    get_personal_tasks, get_tasks_due_soon, mark_reminded, already_reminded,
)

logger = logging.getLogger("privy.scheduler")

# Sleep hours: midnight to 7AM Eastern
SLEEP_HOURS = range(0, 7)
EASTERN = pytz.timezone('America/New_York')


def should_send_now(priority: str) -> bool:
    """
    Decide if an observation should be sent now based on time and priority.
    
    - Sleep hours (midnight-7AM): only critical priority
    - Late night (10PM-midnight): critical and high priority
    - Normal hours (7AM-10PM): all priorities
    """
    now = datetime.now(EASTERN)
    hour = now.hour
    
    if hour in SLEEP_HOURS:
        return priority == "critical"
    
    if hour >= 22:
        return priority in ("critical", "high")
    
    return True


def _trend(current: int, prior: int) -> str:
    """Calculate percentage trend between two values."""
    if prior == 0:
        return "+∞%"
    pct = ((current - prior) / prior) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.0f}%"


async def morning_briefing(send_fn) -> None:
    """
    Send daily morning briefing with YouTube channel data.

    Fetches last 7 days and prior 7 days for trend comparison.
    Formats and sends via Telegram. No LLM unless anomaly detected.
    """
    try:
        # Wait for any in-progress polls before reading time-sensitive data
        # Max 5s each — don't block briefing
        await polling_manager.wait_for("gmail_personal", timeout=5.0)
        await polling_manager.wait_for("gmail_rfd", timeout=5.0)
        await polling_manager.wait_for("calendar_today", timeout=5.0)
        await polling_manager.wait_for("google_tasks", timeout=5.0)

        today = datetime.now()
        week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        week_end = today.strftime("%Y-%m-%d")

        # Flush overnight queue first
        queued = flush_morning_queue()
        if queued:
            msg = f"📺 Good morning Robert.\n\nOvernight alerts:\n"
            for obs in queued:
                msg += f"• {obs['message']}\n"
            msg += "\n"
        else:
            msg = f"📺 Good morning Robert.\n\n"

        # Current week
        current = get_channel_summary(days=7)
        if "error" in current:
            await send_fn(f"📺 Morning briefing failed: {current['error']}")
            return

        # Prior week for trend
        prior_start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
        prior_end = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        prior = get_channel_summary_range(prior_start, prior_end)
        if "error" in prior:
            await send_fn(f"📺 Morning briefing failed: {prior['error']}")
            return

        # Calculate trends
        views_trend = _trend(current["views"], prior["views"])

        # Anomaly detection
        anomaly = False
        if prior["views"] > 0:
            ratio = current["views"] / prior["views"]
            anomaly = ratio > 3.0 or ratio < 0.5

        # Format message
        msg += (
            f"Channel — Last 7 days\n"
            f"Views: {current['views']:,} ({views_trend} vs prior week)\n"
            f"Watch time: {current['watch_time_minutes']:.0f} min\n"
            f"Subscribers: +{current['subscribers_gained']}\n"
        )

        if anomaly:
            msg += "\n⚡ Anomaly detected — check analytics"
        else:
            msg += "\nNo anomalies. Good day to build."

        # Check for game history trends (tracked games with >10% player change)
        # Tracked games: Raccoin (appid from prior calls), Duckov, etc.
        # For now, check games with recent history
        try:
            from tools.games.metrics import get_game_metrics
            tracked_games = ["Raccoin", "Duckov", "Scritchy Scratchy"]
            for game_name in tracked_games:
                try:
                    metrics = get_game_metrics(game_name)
                    if "error" not in metrics and "players_change_pct" in metrics:
                        change = metrics["players_change_pct"]
                        if abs(change) > 10:
                            msg += f"\n⚡ {game_name}: {metrics['players_2weeks']:,} players ({change:+.1f}% vs last week)"
                except Exception:
                    pass
        except Exception:
            pass

        # Check for scheduled videos today
        try:
            scheduled = get_scheduled_videos()
            today_str = today.strftime("%Y-%m-%d")
            for vid in scheduled:
                vid_date = vid["scheduled_time"][:10] if vid["scheduled_time"] else ""
                if vid_date == today_str:
                    msg += f"\n📅 Scheduled today: {vid['title']} at {vid['scheduled_time'][11:16]}"
        except Exception:
            pass

        # Add today's calendar events
        try:
            schedule = get_today_schedule()
            if schedule["count"] > 0:
                lines = "\n".join(schedule["formatted"][:5])
                msg += f"\n\n\U0001f4c5 Today:\n{lines}"
        except Exception as e:
            logger.debug(f"Calendar check failed: {e}")

        # Add email unread counts (both accounts)
        try:
            inbox = get_all_inbox_summary()
            lines = []
            personal_count = inbox["personal"]["unread_count"]
            if personal_count > 0:
                senders = list({
                    m["from"].split("<")[0].strip()[:20]
                    for m in inbox["personal"]["recent"]
                })[:2]
                sender_str = f" \u2014 {', '.join(senders)}" if senders else ""
                lines.append(f"Personal: {personal_count} unread{sender_str}")
            rfd_count = inbox["professional"]["unread_count"]
            if rfd_count > 0:
                senders = list({
                    m["from"].split("<")[0].strip()[:20]
                    for m in inbox["professional"]["recent"]
                })[:2]
                sender_str = f" \u2014 {', '.join(senders)}" if senders else ""
                lines.append(f"RFD IT: {rfd_count} unread{sender_str}")
            if lines:
                msg += "\n" + "\n".join(f"\U0001f4ec {l}" for l in lines)
        except Exception as e:
            logger.debug(f"Gmail check failed: {e}")

        # Add today's tasks section
        try:
            tasks_today = get_tasks_due_today()
            if tasks_today:
                msg += f"\n\n📋 Today's Tasks ({len(tasks_today)}):"
                for task in tasks_today:
                    status_icon = "✓" if task["status"] == "complete" else "○"
                    msg += f"\n{status_icon} {task['title']}"
                    if task.get("scheduled_at"):
                        msg += f" at {task['scheduled_at'][11:16]}"
        except Exception as e:
            logger.debug(f"Tasks check failed: {e}")

        # Add personal tasks today
        try:
            personal_today = get_personal_tasks("today")
            if personal_today:
                task_lines = "\n".join(
                    f"○ {t['title']}" + (f" at {t['due_time']}" if t.get("due_time") else "")
                    for t in personal_today
                )
                msg += f"\n\n📝 Personal tasks today:\n{task_lines}"
        except Exception as e:
            logger.debug(f"Personal tasks check failed: {e}")

        # Add weekly focus
        try:
            weekly_plan = get_current_weekly_plan()
            if weekly_plan:
                msg += f"\n\n🎯 Weekly Focus: {weekly_plan['focus']}"
        except Exception as e:
            logger.debug(f"Weekly plan check failed: {e}")

        await send_fn(msg)
        logger.info("Morning briefing sent successfully")

        # Record to channel history
        today_str = today.strftime("%Y-%m-%d")
        record_channel_day(
            date=today_str,
            views=current["views"],
            watch_time=current["watch_time_minutes"],
            subs=current["subscribers_gained"]
        )
        logger.info(f"Channel history recorded for {today_str}")

    except Exception as e:
        logger.error(f"Morning briefing failed: {e}")
        await send_fn("📺 Morning briefing failed: Unexpected error")


async def check_missed_briefing(send_fn) -> None:
    """
    Called on every startup.
    If current time is past 7AM and no channel_history entry exists for today —
    the briefing was missed. Send it now.
    """
    now = datetime.now(EASTERN)
    
    if now.hour < 7:
        return  # Before briefing time, skip
    
    today = now.strftime("%Y-%m-%d")
    history = get_channel_history(days=1)
    
    already_sent = any(
        h["date"] == today for h in history
    )
    
    if not already_sent:
        logger.info("Missed briefing detected. Sending now.")
        await morning_briefing(send_fn)


async def heartbeat_check(send_fn) -> None:
    """
    Hourly heartbeat check for proactive observations.
    
    Checks:
    - Commitments due today
    - Content calendar gap
    - Game player count spikes
    - Tasks scheduled in next 60 minutes
    - Overdue tasks
    - Flushes pending queue based on time/priority
    """
    try:
        now = datetime.now(EASTERN)
        observations = []
        
        # Check 1 — content calendar gap
        try:
            scheduled = get_scheduled_videos()
            if scheduled:
                last_scheduled = max(
                    datetime.fromisoformat(s["scheduled_time"].replace("Z", "+00:00"))
                    for s in scheduled
                )
                days_until_gap = (last_scheduled - now).days
                
                if days_until_gap <= 3:
                    queue_observation(
                        "content_gap",
                        f"⚠️ Content gap in {days_until_gap} days. Nothing scheduled after {last_scheduled.strftime('%Y-%m-%d')}.",
                        priority="high"
                    )
                elif days_until_gap <= 7:
                    queue_observation(
                        "content_gap",
                        f"📅 Content gap approaching in {days_until_gap} days",
                        priority="normal"
                    )
        except Exception as e:
            logger.debug(f"Content gap check failed: {e}")
        
        # Check 3 — game trend spike
        try:
            from infra.db import get_game_history
            from tools.games.metrics import get_game_metrics
            tracked_games = ["Raccoin", "Duckov"]
            
            for game_name in tracked_games:
                try:
                    metrics = get_game_metrics(game_name)
                    if "error" not in metrics and "players_change_pct" in metrics:
                        change = metrics["players_change_pct"]
                        if abs(change) > 20:
                            queue_observation(
                                "game_spike",
                                f"⚡ {game_name}: {metrics['players_2weeks']:,} players ({change:+.1f}% this week)",
                                priority="normal"
                            )
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Game trend check failed: {e}")
        
        # Check 4 — tasks scheduled in next 60 minutes
        try:
            upcoming = get_upcoming_scheduled(hours=1)
            for task in upcoming:
                if task.get("scheduled_at"):
                    scheduled_time = datetime.fromisoformat(task["scheduled_at"])
                    minutes_until = (scheduled_time - now).total_seconds() / 60
                    if 0 < minutes_until <= 60:
                        await send_fn(f"⏰ Reminder: {task['title']} in {int(minutes_until)} minutes")
                        logger.info(f"Sent task reminder: {task['title']}")
        except Exception as e:
            logger.debug(f"Task reminder check failed: {e}")
        
        # Check 5 — overdue tasks
        try:
            today = now.strftime("%Y-%m-%d")
            overdue = get_tasks(status="pending")
            for task in overdue:
                if task["due_date"] < today:
                    queue_observation(
                        "overdue_task",
                        f"⚠️ Overdue: {task['title']} was due {task['due_date']}",
                        priority="high"
                    )
        except Exception as e:
            logger.debug(f"Overdue task check failed: {e}")
        
        # Check 6 — flush pending queue
        pending = get_pending_observations()
        for obs in pending:
            if should_send_now(obs["priority"]):
                await send_fn(obs["message"])
                mark_sent(obs["id"])
                logger.info(f"Sent queued observation: {obs['task_name']}")

        # Check 7 — personal task reminders
        try:
            tasks_soon = get_tasks_due_soon(minutes=90)
            now = datetime.now()
            for task in tasks_soon:
                if not already_reminded(task["id"]):
                    if task.get("due_datetime"):
                        try:
                            due_dt = datetime.fromisoformat(
                                task["due_datetime"].replace(" ", "T")
                            )
                            minutes_left = int((due_dt - now).total_seconds() / 60)
                        except Exception:
                            minutes_left = None
                    else:
                        minutes_left = None
                    label = f"In ~{minutes_left}min: " if minutes_left is not None else ""
                    await send_fn(f"\U0001f514 {label}{task['title']}")
                    mark_reminded(task["id"])
                    logger.info(f"Sent personal task reminder: {task['title']}")
        except Exception as e:
            logger.debug(f"Personal task reminder check failed: {e}")

        # Check 10 — pre-event calendar alerts
        try:
            import zlib
            raw = get_events_soon(minutes=60)
            events_soon = raw.get("events", [])
            for event in events_soon:
                alert_key = f"cal_{event['id']}_{event['start'][:10]}"
                alert_id = zlib.adler32(alert_key.encode()) & 0x7FFFFFFF
                if not already_reminded(alert_id):
                    mins = event.get("minutes_until")
                    label = f"In ~{mins}min: " if mins is not None else ""
                    msg = f"\U0001f4c5 {label}{event['title']}"
                    if event.get("location"):
                        msg += f"\n\U0001f4cd {event['location']}"
                    if should_send_now("high"):
                        await send_fn(msg)
                        mark_reminded(alert_id)
                        logger.info(f"Sent calendar alert: {event['title']}")
        except Exception as e:
            logger.debug(f"Calendar alert check failed: {e}")

        # Check 9 — overdue and pending personal task reminder (daily summary only)
        try:
            # Use a unique alert key for the daily summary
            summary_alert_key = f"daily_task_summary_{now.strftime('%Y-%m-%d')}"
            import zlib
            summary_alert_id = zlib.adler32(summary_alert_key.encode()) & 0x7FFFFFFF
            
            if not already_reminded(summary_alert_id):
                overdue_tasks = get_personal_tasks("overdue")
                today_pending = get_personal_tasks("today")

                if overdue_tasks and should_send_now("normal"):
                    lines = "\n".join(
                        f"\u2022 {t['title']}" for t in overdue_tasks[:5]
                    )
                    await send_fn(f"\u26a0\ufe0f Overdue ({len(overdue_tasks)}):\n{lines}")

                if today_pending and should_send_now("normal"):
                    lines = "\n".join(
                        f"\u2022 {t['title']}" + (f" at {t['due_time']}" if t.get("due_time") else "")
                        for t in today_pending[:5]
                    )
                    await send_fn(
                        f"\U0001f4dd Still pending today ({len(today_pending)}):\n{lines}"
                    )
                
                # Mark this daily summary as sent
                mark_reminded(summary_alert_id)
        except Exception as e:
            logger.debug(f"Personal task reminder check failed: {e}")

        logger.info("Heartbeat check complete")
        
    except Exception as e:
        logger.error(f"Heartbeat check failed: {e}")


async def auto_rollback(send_fn) -> None:
    """
    Called by health_check when critical failure detected.
    Reverts to last stable commit, verifies, restarts service.
    """
    stable = get_last_stable_commit()
    if not stable:
        await send_fn("🔴 Auto-rollback failed: no stable commit recorded.")
        return

    await send_fn(
        f"⚠️ Health check failed. "
        f"Auto-rolling back to {stable['commit_hash'][:7]}..."
    )

    result = subprocess.run(
        ["git", "checkout", stable["commit_hash"]],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        await send_fn(f"🔴 Auto-rollback failed: {result.stderr.strip()}")
        return

    try:
        subprocess.run(["nssm", "restart", "PrivyBot"], capture_output=True)
    except FileNotFoundError:
        pass

    deploy_id = record_deploy(stable["commit_hash"], f"auto-rollback: {stable['commit_message']}")
    mark_verify_passed(deploy_id)
    mark_stable(deploy_id)

    await send_fn(
        f"↩️ Auto-rolled back to {stable['commit_hash'][:7]}. "
        f"Service restarted."
    )


async def health_check(send_fn) -> None:
    """
    Runs every hour alongside heartbeat.
    Checks model availability, YouTube credentials, database, and last deploy status.
    Auto-rolls back on critical failure.
    """
    issues = []

    # Check 1 — can we reach OpenRouter (any model available)?
    try:
        from bot.model_manager import get_available_model
        model = get_available_model()
        if model is None:
            issues.append("No free models available")
    except Exception as e:
        issues.append(f"Model manager error: {e}")

    # Check 2 — YouTube credentials accessible?
    try:
        from api.google.youtube_api import _get_credentials
        creds = _get_credentials()
        if creds is None:
            issues.append("YouTube credentials missing")
    except Exception as e:
        issues.append(f"YouTube credentials error: {e}")

    # Check 3 — database accessible?
    try:
        from infra.db import list_memories
        list_memories()
    except Exception as e:
        issues.append(f"Database error: {e}")

    # Check 4 — did last deploy pass verify?
    try:
        last_deploy = get_last_deploy()
        if last_deploy and not last_deploy["verify_passed"]:
            issues.append("Last deploy did not pass verify")
            await auto_rollback(send_fn)
            return
    except Exception as e:
        issues.append(f"Deploy history error: {e}")

    if issues:
        msg = "🟡 Health check: " + ", ".join(issues)
        await send_fn(msg)
        logger.warning(f"Health check issues: {issues}")
    else:
        logger.info("Health check clean")


async def run_scheduler(send_fn) -> None:
    """
    Run the scheduler with fixed tasks and hourly heartbeat.

    Fixed tasks:
    - 07:00: morning_briefing
    - 23:59: nightly_summary (if implemented)

    Heartbeat:
    - Every 60 minutes: heartbeat_check
    """
    # Track which tasks have fired today
    fired_today = {}
    last_heartbeat = None
    
    while True:
        now = datetime.now(EASTERN)
        today_str = now.strftime("%Y-%m-%d")
        
        # Reset fired_today at midnight
        if fired_today.get("date") != today_str:
            fired_today = {"date": today_str}
        
        # Check fixed tasks
        tasks = [
            ("07:00", "morning_briefing", morning_briefing),
            ("23:59", "nightly_summary", None),  # Placeholder for nightly_summary
        ]
        
        for time_str, task_name, task_fn in tasks:
            if task_fn is None:
                continue
                
            target = now.replace(
                hour=int(time_str[:2]),
                minute=int(time_str[3:]),
                second=0,
                microsecond=0
            )
            
            # If target is in the past, move to tomorrow
            if now >= target:
                target += timedelta(days=1)
            
            # If we're within 1 minute of target and haven't fired today
            if abs((now - target).total_seconds()) < 60 and task_name not in fired_today:
                try:
                    await task_fn(send_fn)
                    fired_today[task_name] = True
                    logger.info(f"Executed scheduled task: {task_name}")
                except Exception as e:
                    logger.error(f"Task {task_name} failed: {e}")
        
        # Heartbeat + health check — run every 60 minutes
        if last_heartbeat is None or (now - last_heartbeat).total_seconds() >= 3600:
            try:
                await heartbeat_check(send_fn)
                last_heartbeat = now
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
            try:
                await health_check(send_fn)
            except Exception as e:
                logger.error(f"Health check failed: {e}")
        
        # Sleep for 1 minute before next check
        await asyncio.sleep(60)
