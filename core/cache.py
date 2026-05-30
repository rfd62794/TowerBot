"""
core/cache.py

Single owner of all cache behavior.
Import the singleton:
  from core.cache import cache

Usage:
  result = cache.call("weather", hash, fn)
  notice = cache.stale_notice(result)
"""

import json
import time
import hashlib
import logging
from typing import Callable
from datetime import datetime

logger = logging.getLogger("privy.cache")


class CacheManager:

    # ─── Canonical TTL registry ───────────
    # Source of truth for ALL cache TTLs.
    # Phase 2 API files read from here.
    # Values in seconds.
    TTL = {
        "youtube_channel": 86400,  # 24h
        "youtube_videos": 21600,  # 6h
        "youtube_analytics": 86400,  # 24h
        "youtube_traffic": 86400,  # 24h
        "youtube_demographics": 86400,
        "youtube_retention": 86400,
        "youtube_devices": 86400,
        "youtube_daily": 21600,  # 6h
        "youtube_geography": 86400,
        "youtube_playlist_id": 86400,  # 24h
        "youtube_playlist_items": 86400,  # 24h
        "gmail_personal": 300,  # 5min
        "gmail_rfd": 300,  # 5min
        "calendar_today": 900,  # 15min
        "calendar_upcoming": 900,  # 15min
        "google_tasks": 300,  # 5min
        "steam_library": 86400,  # 24h
        "steam_metrics": 7200,  # 2h
        "steamspy": 14400,  # 4h
        "itad_prices": 7200,  # 2h
        "weather": 3600,  # 1h
        "ddg_search": 1800,  # 30min
        "wikipedia": 86400,  # 24h
        "reddit": 900,  # 15min
    }

    # ─── Staleness budget ─────────────────
    # How old is "too old" to show user.
    # After this age — stale_notice shown.
    # Usually matches TTL but can differ.
    STALE_BUDGET = {
        "gmail_personal": 300,
        "gmail_rfd": 300,
        "calendar_today": 900,
        "google_tasks": 300,
        "weather": 3600,
        "ddg_search": 1800,
        "reddit": 900,
        "youtube_channel": 86400,
        "steam_library": 86400,
        "wikipedia": 86400,
        "steamspy": 14400,
        "itad_prices": 7200,
        "steam_metrics": 7200,
        "youtube_videos": 21600,
        "youtube_analytics": 86400,
        "youtube_traffic": 86400,
        "youtube_demographics": 86400,
        "youtube_retention": 86400,
        "youtube_devices": 86400,
        "youtube_daily": 21600,
        "youtube_geography": 86400,
        "youtube_playlist_id": 86400,
        "youtube_playlist_items": 86400,
        "calendar_upcoming": 900,
    }

    # ─── Core methods ─────────────────────

    def hash(self, *args, **kwargs) -> str:
        """
        Deterministic params hash.
        Use for fixed-param calls:
          cache.hash()  ← no params
          cache.hash("duckov")  ← one param
          cache.hash(days=7)  ← kwargs
        """
        key = json.dumps(
            {"args": list(args), "kwargs": kwargs},
            sort_keys=True, default=str
        )
        return hashlib.md5(key.encode()).hexdigest()

    def get(self, key: str, params_hash: str) -> dict | None:
        """
        Fresh cache hit only.
        Returns None if miss or expired.
        Does NOT return stale data.
        """
        from core.db.cache import get_cached_tool_result
        result = get_cached_tool_result(key, params_hash)
        if result is None:
            return None
        result["_stale"] = False
        return result

    def get_or_stale(self, key: str, params_hash: str) -> dict | None:
        """
        Fresh first. Stale if expired.
        None only if never cached.
        """
        fresh = self.get(key, params_hash)
        if fresh is not None:
            return fresh
        from core.db.cache import get_stale_cached_result
        return get_stale_cached_result(key, params_hash)

    def set(self, key: str, params_hash: str, data: dict) -> None:
        """
        Store with TTL from TTL policy.
        Unknown keys default to 3600s.
        """
        from core.db.cache import cache_tool_result
        ttl = self.TTL.get(key, 3600)
        data["_stale"] = False
        cache_tool_result(key, params_hash, data, ttl)

    def call(self, key: str, params_hash: str, live_fn: Callable, stale_ok: bool = True) -> dict:
        """
        Main entry point for all API calls.

        1. Fresh cache hit → return immediately
        2. Live call succeeds → cache + return
        3. Live fails + stale_ok + stale exists → return stale with metadata
        4. Live fails, no stale → error dict

        TTL comes from self.TTL[key].
        """
        # Step 1 — fresh hit
        cached = self.get(key, params_hash)
        if cached is not None:
            logger.debug(f"[cache] HIT {key}")
            return cached

        # Step 2 — live call
        start = time.time()
        try:
            result = live_fn()
            duration_ms = int((time.time() - start) * 1000)

            if not isinstance(result, dict):
                result = {"value": result}

            self.set(key, params_hash, result)

            logger.debug(f"[cache] LIVE {key} ({duration_ms}ms)")
            return result

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            logger.warning(f"[cache] LIVE FAIL {key}: {e}")

            # Step 3 — stale fallback
            if stale_ok:
                stale = self.get_or_stale(key, params_hash)
                if stale is not None:
                    logger.info(
                        f"[cache] STALE {key} ({stale.get('_age_minutes', '?')}min)"
                    )
                    return stale

            # Step 4 — total failure
            return {"error": str(e), "_live_failed": True, "_stale": False}

    def stale_notice(self, result: dict) -> str | None:
        """
        Human-readable staleness notice.
        Returns None if fresh data.
        """
        if not result.get("_stale"):
            return None

        age = result.get("_age_minutes", 0)
        ts = result.get("_cached_at", "")[:16]

        if age < 60:
            age_str = f"{age}m ago"
        elif age < 1440:
            age_str = f"{age // 60}h ago"
        else:
            age_str = f"{age // 1440}d ago"

        return f"⚠️ Data from {age_str} ({ts})"

    def invalidate(self, key: str, params_hash: str = None) -> None:
        """
        Clear cached data.
        params_hash=None clears all entries for that key.
        """
        from core.db.manager import db
        if params_hash:
            db.exec(
                """
                DELETE FROM tool_cache
                WHERE tool_name = ?
                  AND params_hash = ?
            """,
                [key, params_hash],
            )
        else:
            db.exec(
                """
                DELETE FROM tool_cache
                WHERE tool_name = ?
            """,
                [key],
            )
        logger.info(f"[cache] INVALIDATED {key}")

    def status(self) -> list[dict]:
        """
        Health of all cached tools.
        Returns last fetch time and age for every known tool.
        """
        from core.db.cache import get_preload_status
        preload = get_preload_status()
        preload_map = {p["tool_name"]: p for p in preload}

        results = []
        for key in sorted(self.TTL.keys()):
            ttl = self.TTL[key]
            budget = self.STALE_BUDGET.get(key, ttl)
            preload_info = preload_map.get(key)

            results.append(
                {
                    "key": key,
                    "ttl_seconds": ttl,
                    "stale_budget_seconds": budget,
                    "last_preload": preload_info["last_fetch"] if preload_info else None,
                    "last_preload_age_minutes": (
                        preload_info["age_minutes"] if preload_info else None
                    ),
                    "last_preload_success": preload_info["success"] if preload_info else None,
                }
            )

        return results

    def preload(self, tasks: list[dict]) -> dict:
        """
        Warm cache from task list.
        Each task: {
            "key": str,
            "fn": callable,
            "params_hash": str,
        }
        Runs sequentially.
        Returns summary dict.
        """
        loaded = 0
        failed = 0
        results = []

        for task in tasks:
            key = task["key"]
            fn = task["fn"]
            ph = task.get("params_hash", self.hash())

            start = time.time()
            try:
                result = fn()
                duration_ms = int((time.time() - start) * 1000)

                if isinstance(result, dict):
                    self.set(key, ph, result)
                    loaded += 1
                    ok = True
                else:
                    failed += 1
                    ok = False

            except Exception as e:
                duration_ms = int((time.time() - start) * 1000)
                logger.warning(f"[cache] PRELOAD FAIL {key}: {e}")
                failed += 1
                ok = False

            results.append({"key": key, "ok": ok, "duration_ms": duration_ms})

        return {"loaded": loaded, "failed": failed, "results": results}


# ─── Singleton ────────────────────────────
# All other layers import this instance.
# from core.cache import cache
cache = CacheManager()
