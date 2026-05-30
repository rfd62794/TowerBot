"""Scheduler — background tasks for periodic operations."""

import asyncio
import logging
from datetime import datetime, timedelta

from tools.youtube import get_channel_summary, get_channel_summary_range
from core.db import record_channel_day, get_game_history, get_scheduled_videos

logger = logging.getLogger("privy.scheduler")


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
        today = datetime.now()
        week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        week_end = today.strftime("%Y-%m-%d")

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
        msg = (
            f"📺 Good morning Robert.\n\n"
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
            from tools.games import get_game_metrics
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


async def run_scheduler(send_fn) -> None:
    """
    Run the morning briefing scheduler.

    Wakes up at 7AM daily and sends the briefing.
    Runs as a background asyncio task.
    """
    while True:
        now = datetime.now()
        # Next 7AM
        target = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        logger.info(f"Next briefing in {wait_seconds / 3600:.1f} hours at {target}")
        await asyncio.sleep(wait_seconds)

        try:
            await morning_briefing(send_fn)
        except Exception as e:
            logger.error(f"Briefing failed: {e}")
