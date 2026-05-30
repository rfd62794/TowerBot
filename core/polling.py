"""
core/polling.py

Single owner of all polling behavior.
Replaces heartbeat data fetching.
Each data source polls at its own interval.
Coordinates with CacheManager and RateLimitManager before every poll.

Import the singleton:
  from core.polling import polling_manager

Usage:
  polling_manager.register(
      key="gmail_personal",
      fn=get_inbox_summary,
      interval_seconds=300,
      args={"account": "personal"}
  )
  asyncio.create_task(polling_manager.run_loop())
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Callable

logger = logging.getLogger("privy.polling")


class PollingManager:
    """
    Single owner of all polling behavior.
    Replaces scattered heartbeat checks.
    Each data source has its own interval.
    Coordinates with Cache + RateLimit.
    """

    # Default poll intervals — match TTLs from CacheManager exactly.
    # None = on-demand only, never polled.
    INTERVALS = {
        "gmail_personal": 300,
        "gmail_rfd": 300,
        "calendar_today": 900,
        "calendar_upcoming": 900,
        "google_tasks": 300,
        "youtube_channel": 86400,
        "steam_library": 86400,
        "weather": 3600,
        "ddg_search": None,
        "wikipedia": None,
        "reddit": None,
    }

    def __init__(self):
        # Registered polls: key → {fn, args, interval_seconds}
        self._registry: dict = {}

        # In-progress poll signals: key → asyncio.Event
        self._poll_events: dict[str, asyncio.Event] = {}

        self._running = False

    # ─── Registration ──────────────────────

    def register(self,
                 key: str,
                 fn: Callable,
                 interval_seconds: int = None,
                 args: dict = None) -> None:
        """
        Register a data source for polling.
        interval_seconds: None = on-demand only
        args: kwargs passed to fn on each poll
        """
        self._registry[key] = {
            "fn": fn,
            "args": args or {},
            "interval_seconds": interval_seconds or self.INTERVALS.get(key),
        }
        logger.debug(f"[poll] registered {key} every {interval_seconds}s")

    def register_defaults(self) -> None:
        """
        Register all default data sources.
        Called at startup from privybot.py.
        Imports here to avoid circular imports.
        """
        from tools.gmail import get_inbox_summary
        from tools.calendar import get_today_schedule
        from tools.calendar import get_upcoming_events
        from tools.sync_tasks import run_sync
        from tools.youtube.channel import get_channel_summary
        from tools.games import get_installed_games
        from tools.search_tools import get_weather

        self.register(
            "gmail_personal",
            get_inbox_summary,
            interval_seconds=300,
            args={"account": "personal"}
        )

        self.register(
            "gmail_rfd",
            get_inbox_summary,
            interval_seconds=300,
            args={"account": "rfd"}
        )

        self.register(
            "calendar_today",
            get_today_schedule,
            interval_seconds=900
        )

        self.register(
            "calendar_upcoming",
            get_upcoming_events,
            interval_seconds=900
        )

        self.register(
            "google_tasks",
            run_sync,
            interval_seconds=300
        )

        self.register(
            "youtube_channel",
            get_channel_summary,
            interval_seconds=86400,
            args={"days": 7}
        )

        self.register(
            "steam_library",
            get_installed_games,
            interval_seconds=86400
        )

        self.register(
            "weather",
            get_weather,
            interval_seconds=3600
        )

    # ─── Core loop ─────────────────────────

    async def run_loop(self) -> None:
        """
        Main poll loop. Runs indefinitely.
        Checks every 60s which polls are due.
        Fires due polls as async tasks.
        """
        self._running = True
        logger.info("[poll] loop started")

        while self._running:
            now = datetime.now()

            for key, config in self._registry.items():
                interval = config["interval_seconds"]

                if interval is None:
                    continue  # on-demand only

                if await self._is_due(key, interval, now):
                    asyncio.create_task(self._run_poll(key))

            await asyncio.sleep(60)

    async def _is_due(self,
                      key: str,
                      interval: int,
                      now: datetime) -> bool:
        """
        Is this poll due to run?
        Checks last_polled_at from DB.
        Also checks CacheManager — if cache is still fresh, skip the poll.
        """
        from core.db.polling_db import get_last_poll
        from core.cache import cache
        from core.rate_limits import rate_limits

        # Rate limited — skip
        api_prefix = key.split("_")[0]
        if not rate_limits.can_call(api_prefix):
            return False

        # Check last poll time
        last = get_last_poll(key)
        if last is None:
            return True  # never polled

        last_at = datetime.fromisoformat(last["polled_at"])
        due_at = last_at + timedelta(seconds=interval)

        return now >= due_at

    async def _run_poll(self, key: str) -> None:
        """
        Execute one poll.
        Sets asyncio.Event while in progress.
        Callers can wait_for() this key.
        """
        from core.db.polling_db import record_poll

        if key in self._poll_events:
            return  # already polling this key

        event = asyncio.Event()
        self._poll_events[key] = event

        config = self._registry.get(key)
        if not config:
            event.set()
            del self._poll_events[key]
            return

        fn = config["fn"]
        args = config["args"]
        start = time.time()

        try:
            logger.debug(f"[poll] firing {key}")

            # Run in executor to not block loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: fn(**args))

            duration_ms = int((time.time() - start) * 1000)

            # Check if result was from cache (has _stale key)
            from_cache = bool(result and not result.get("_stale"))

            record_poll(
                key,
                success=True,
                duration_ms=duration_ms,
                from_cache=from_cache
            )

            logger.info(f"[poll] {key} ok ({duration_ms}ms)")

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)

            record_poll(
                key,
                success=False,
                duration_ms=duration_ms,
                error_msg=str(e)[:200]
            )

            logger.warning(f"[poll] {key} failed: {e}")

        finally:
            event.set()  # always signal waiters
            if key in self._poll_events:
                del self._poll_events[key]

    # ─── Coordination ──────────────────────

    async def wait_for(self,
                       key: str,
                       timeout: float = 5.0) -> bool:
        """
        Wait for an in-progress poll.
        Returns True if completed.
        Returns False if timeout or not polling.
        Called by morning_briefing for time-sensitive keys.
        """
        event = self._poll_events.get(key)
        if event is None:
            return True  # not polling

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning(f"[poll] wait_for {key} timed out after {timeout}s")
            return False

    # ─── Status ────────────────────────────

    def status(self) -> list[dict]:
        """
        Current state of all registered polls.
        Used by /status command.
        """
        from core.db.polling_db import get_all_last_polls

        last_polls = {p["poll_key"]: p for p in get_all_last_polls()}

        now = datetime.now()
        results = []

        for key, config in self._registry.items():
            interval = config["interval_seconds"]
            last = last_polls.get(key)

            next_due = None
            overdue = False

            if last and interval:
                last_at = datetime.fromisoformat(last["polled_at"])
                next_due_dt = last_at + timedelta(seconds=interval)
                next_due = next_due_dt.strftime("%Y-%m-%d %H:%M:%S")
                overdue = now > next_due_dt

            results.append({
                "key": key,
                "interval_seconds": interval,
                "last_polled": last["polled_at"] if last else None,
                "last_success": bool(last["success"]) if last else None,
                "next_due": next_due,
                "overdue": overdue,
                "in_progress": key in self._poll_events
            })

        return results

    def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False


# ─── Singleton ────────────────────────────
polling_manager = PollingManager()
