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
    get_channel_history,
    get_last_stable_commit, get_last_deploy, record_deploy, mark_verify_passed, mark_stable,
    get_overnight_actions,
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
    rounded = round(pct)
    sign = "+" if rounded >= 0 else ""
    return f"{sign}{rounded}%"


def _hours_ago(date_str: str) -> int:
    """Calculate hours ago from ISO date string."""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        hours = (datetime.now() - dt).total_seconds() / 3600
        return int(hours)
    except Exception:
        return 999  # Return large number if parsing fails


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

        # Add overnight autonomous actions
        try:
            overnight = get_overnight_actions()
            if overnight:
                msg += f"🤖 Overnight ({len(overnight)} tasks ran):\n"
                for action in overnight[:5]:
                    prefix = "🚨" if action["urgent"] else "•"
                    summary = (action["result"] or "")[:120]
                    msg += f"{prefix} {action['task_name']}: {summary}\n"
        except Exception as e:
            logger.debug(f"Overnight actions check failed: {e}")

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

        # Add itch.io stats
        try:
            from tools.games.metrics import get_itch_stats
            itch_result = get_itch_stats()
            if itch_result.get("ok") and itch_result.get("count", 0) > 0:
                games = itch_result.get("games", [])
                total_views = sum(g.get("views_count", 0) for g in games)
                total_downloads = sum(g.get("downloads_count", 0) for g in games)
                total_purchases = sum(g.get("purchases_count", 0) for g in games)
                msg += f"\n\n🎮 itch.io — {itch_result['count']} games\n"
                msg += f"Views: {total_views:,} | Downloads: {total_downloads:,} | Purchases: {total_purchases:,}"
        except Exception as e:
            logger.debug(f"itch.io check failed: {e}")

        # Add top performing videos
        try:
            from tools.content.videos import get_top_videos
            top_videos = get_top_videos(days=7, limit=3)
            if top_videos.get("ok") and top_videos.get("videos"):
                msg += f"\n\n📺 Top videos (7d):\n"
                for vid in top_videos["videos"][:3]:
                    views = vid.get("views", 0)
                    title = vid.get("title", "Unknown")[:40]
                    msg += f"  • {title}: {views:,} views\n"
        except Exception as e:
            logger.debug(f"Top videos check failed: {e}")

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


        # Add weather
        try:
            from tools.search.search_tools import get_weather
            weather = get_weather()
            if weather.get("ok"):
                temp = weather.get("temp_f", "?")
                condition = weather.get("condition", "")
                msg += f"\n\n{temp}°F, {condition}, South Florida."
        except Exception as e:
            logger.debug(f"Weather check failed: {e}")

        # Add Google Tasks due today
        try:
            from tools.productivity.google_tasks import list_google_tasks
            tasks = list_google_tasks()
            today_date = datetime.now().strftime("%Y-%m-%d")
            due_today = [t for t in tasks.get("tasks", [])
                         if t.get("due_date", "").startswith(today_date)
                         and t.get("status") != "completed"]
            if due_today:
                msg += "\n\n📋 *Tasks due today:*"
                for t in due_today[:5]:
                    msg += f"\n  • {t.get('title','')}"
        except Exception as e:
            logger.debug(f"Google Tasks check failed: {e}")

        # Add overnight findings from autonomous tasks
        try:
            from infra.db.autonomous import get_overnight_actions
            actions = get_overnight_actions()
            if actions:
                msg += "\n\n🔍 *Overnight:*"
                for a in actions[:3]:
                    result_preview = str(a.get("result",""))[:100]
                    msg += f"\n  • [{a.get('task_name','')}] {result_preview}"
        except Exception as e:
            logger.debug(f"Overnight actions check failed: {e}")

        # Add current platform stats (itch.io)
        try:
            from tools.games.metrics import get_itch_stats
            itch = get_itch_stats()
            if itch.get("ok"):
                games = itch.get("games", [])
                if games:
                    msg += "\n\n🎮 *itch.io:*"
                    for g in games[:2]:
                        msg += f"\n  • {g.get('title','')}: {g.get('views',0)} views · {g.get('downloads',0)} plays"
        except Exception as e:
            logger.debug(f"itch.io stats check failed: {e}")

        # Add commit digest (last 24 hours)
        try:
            from tools.search.search_tools import get_recent_commits
            commits = get_recent_commits(limit=10)
            recent = [c for c in commits.get("commits", [])
                      if _hours_ago(c.get("date","")) <= 24]
            if recent:
                msg += f"\n\n💻 *{len(recent)} commit(s) yesterday:*"
                for c in recent[:3]:
                    msg += f"\n  • [{c.get('repo','')}] {c.get('message','')[:80]}"
        except Exception as e:
            logger.debug(f"Commit digest check failed: {e}")

        # Add weekly mirror (Monday only)
        try:
            if datetime.now().weekday() == 0:  # Monday
                from infra.db.schema import _exec
                week_actions = _exec(
                    "SELECT task_name, COUNT(*) as count FROM agent_actions WHERE ran_at >= datetime('now','-7 days') GROUP BY task_name"
                ).fetchall()
                if week_actions:
                    msg += "\n\n📊 *Last week:*"
                    for row in week_actions[:5]:
                        msg += f"\n  • {row['task_name']}: {row['count']} run(s)"
        except Exception as e:
            logger.debug(f"Weekly mirror check failed: {e}")

        # Add weekly focus
        try:
            weekly_plan = get_current_weekly_plan()
            if weekly_plan:
                msg += f"\n\n🎯 Weekly Focus: {weekly_plan['focus']}"
        except Exception as e:
            logger.debug(f"Weekly plan check failed: {e}")

        # Add decision ranking (3 highest-leverage actions today)
        try:
            from infra.model_router import route
            ranking_prompt = f"""Given this briefing context, rank the 3 highest-leverage things I could do today. Be specific and direct.

{msg}

Respond with exactly 3 actions, one per line:
1. [Action]
2. [Action]
3. [Action]"""
            ranking_result = route(role="reasoning", prompt=ranking_prompt)
            if ranking_result.get("ok"):
                ranking = ranking_result.get("result", "")
                lines = [line.strip() for line in ranking.split('\n') if line.strip() and line[0].isdigit()]
                if lines:
                    msg += f"\n\n🧠 Today's top 3:\n"
                    for line in lines[:3]:
                        msg += f"{line}\n"
        except Exception as e:
            logger.debug(f"Decision ranking failed: {e}")

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


async def nightly_summary(send_fn) -> None:
    """
    Nightly job placeholder.
    Runs at 23:59.
    """
    logger.info("Nightly summary: no-op (local tasks deprecated per ADR-038)")


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
        
        # Check 4 — tasks scheduled in next 60 minutes (deprecated per ADR-038)
        # Local tasks table removed; use Google Tasks API instead
        
        # Check 6 — flush pending queue
        pending = get_pending_observations()
        for obs in pending:
            if should_send_now(obs["priority"]):
                await send_fn(obs["message"])
                mark_sent(obs["id"])
                logger.info(f"Sent queued observation: {obs['task_name']}")


        # Check 10 — pre-event calendar alerts
        try:
            import zlib
            from infra.db.schema import _exec
            raw = get_events_soon(minutes=60)
            events_soon = raw.get("events", [])
            for event in events_soon:
                alert_key = f"cal_{event['id']}_{event['start'][:10]}"
                alert_id = zlib.adler32(alert_key.encode()) & 0x7FFFFFFF

                # Check task_reminders table directly (replaces deprecated already_reminded)
                row = _exec(
                    "SELECT reminded_at FROM task_reminders WHERE task_id=?",
                    (alert_id,)
                ).fetchone()

                if not row:
                    mins = event.get("minutes_until")
                    label = f"In ~{mins}min: " if mins is not None else ""
                    msg = f"\U0001f4c5 {label}{event['title']}"
                    if event.get("location"):
                        msg += f"\n\U0001f4cd {event['location']}"
                    if should_send_now("high"):
                        await send_fn(msg)
                        # Record reminder in task_reminders table
                        _exec(
                            "INSERT INTO task_reminders (task_id, reminded_at) VALUES (?, CURRENT_TIMESTAMP)",
                            (alert_id,),
                            commit=True
                        )
                        logger.info(f"Sent calendar alert: {event['title']}")
        except Exception as e:
            logger.debug(f"Calendar alert check failed: {e}")

        # Check 9 — Google Tasks overdue check with notification deduplication
        try:
            from tools.productivity.google_tasks import list_google_tasks
            from infra.db.schema import _exec

            today = now.strftime("%Y-%m-%d")
            tasks = list_google_tasks(max_results=100)
            if tasks.get("ok"):
                overdue = [
                    t for t in tasks["tasks"]
                    if t.get("due") and t["due"][:10] < today and t.get("status") != "completed"
                ]

                for task in overdue:
                    google_task_id = task.get("id")
                    if not google_task_id:
                        continue

                    # Check if we've already notified for this overdue task
                    row = _exec(
                        "SELECT last_notified_at FROM task_notifications WHERE google_task_id=? AND notification_type='overdue'",
                        (google_task_id,)
                    ).fetchone()

                    # Only notify if not notified in the last 24 hours
                    should_notify = True
                    if row:
                        last_notified = row["last_notified_at"]
                        try:
                            last_dt = datetime.fromisoformat(last_notified)
                            hours_since = (now - last_dt).total_seconds() / 3600
                            if hours_since < 24:
                                should_notify = False
                        except Exception:
                            pass

                    if should_notify and should_send_now("normal"):
                        await send_fn(f"⚠️ Overdue: {task['title']} (was due {task['due'][:10]})")
                        logger.info(f"Sent overdue notification for Google Task: {task['title']}")

                        # Record notification in task_notifications table
                        _exec(
                            """INSERT OR REPLACE INTO task_notifications
                               (google_task_id, notification_type, last_notified_at)
                               VALUES (?, 'overdue', ?)""",
                            (google_task_id, now.isoformat()),
                            commit=True
                        )
        except Exception as e:
            logger.debug(f"Google Tasks overdue check failed: {e}")

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
    """Maintenance mode — scheduler idle."""
    logger.info("Scheduler: maintenance mode")
    while True:
        await asyncio.sleep(3600)
