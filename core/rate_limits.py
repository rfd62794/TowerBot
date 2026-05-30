"""
core/rate_limits.py

Single owner of rate limit state.
Consulted by BaseAPIHandler before every live API call.

Import the singleton:
  from core.rate_limits import rate_limits
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger("privy.rate_limits")


class RateLimitManager:

    # ─── Known limits per API ─────────────
    # Source of truth for rate limit policy.
    # None = unknown/unlimited for that field.
    
    LIMITS = {
        "youtube": {
            "units_per_day": 10000,
            "cost_per_search": 100,
            "cost_per_list": 1,
            "requests_per_minute": None,
        },
        "youtube_analytics": {
            "units_per_day": 10000,
            "cost_per_query": 1,
            "requests_per_minute": None,
        },
        "gmail": {
            "requests_per_second": 5,
            "requests_per_day": None,
        },
        "calendar": {
            "requests_per_day": None,
            "requests_per_minute": None,
        },
        "google_tasks": {
            "requests_per_day": None,
            "requests_per_minute": None,
        },
        "steam": {
            "requests_per_5min": 200,
            "requests_per_day": None,
        },
        "steamspy": {
            "requests_per_minute": 4,
            "requests_per_day": None,
        },
        "itad": {
            "requests_per_day": 1000,
            "requests_per_minute": None,
        },
        "ddg": {
            "requests_per_minute": 20,
            "requests_per_day": None,
        },
        "wikipedia": {
            "requests_per_second": 200,
            "requests_per_day": None,
        },
        "reddit": {
            "requests_per_minute": 60,
            "requests_per_day": None,
        },
        "fetch": {
            "requests_per_minute": 60,
            "requests_per_day": None,
        },
        "openrouter": {
            "handled_by": "model_manager",
        }
    }

    # ─── Core methods ─────────────────────

    def can_call(self, api: str) -> bool:
        """
        True if safe to make a live call now.
        
        Checks in order:
        1. Explicit 429 cooldown active?
        2. Per-minute rate exceeded?
        3. Daily quota exceeded? (if known)
        
        Returns True if all checks pass.
        Unknown APIs always return True —
        don't block what we can't measure.
        """
        from core.db.rate_limits_db import get_api_state
        
        state = get_api_state(api)
        now = datetime.now()
        
        # Check 1 — 429 cooldown
        if state["last_429_at"]:
            last_429 = datetime.fromisoformat(state["last_429_at"])
            retry_after = state["retry_after_seconds"] or 60
            cooldown_until = last_429 + timedelta(seconds=retry_after)
            if now < cooldown_until:
                remaining = int((cooldown_until - now).total_seconds())
                logger.debug(f"[rate] {api} in cooldown ({remaining}s remaining)")
                return False
        
        # Check 2 — per-minute limit
        limits = self.LIMITS.get(api, {})
        rpm = limits.get("requests_per_minute")
        
        if rpm and state["last_call_at"]:
            last_call = datetime.fromisoformat(state["last_call_at"])
            if (now - last_call).total_seconds() < 60:
                if state["calls_this_minute"] >= rpm:
                    logger.warning(f"[rate] {api} minute limit reached ({rpm}/min)")
                    return False
        
        # Check 3 — daily quota
        daily = limits.get("units_per_day") or limits.get("requests_per_day")
        
        if daily:
            self._maybe_reset_daily(api, state, now)
            state = get_api_state(api)
            if state["quota_used_today"] >= daily:
                logger.warning(f"[rate] {api} daily quota exhausted ({daily}/day)")
                return False
        
        return True

    def record_call(self, api: str, cost: int = 1) -> None:
        """
        Record a successful API call.
        Updates rolling counters.
        """
        from core.db.rate_limits_db import (
            get_api_state, upsert_api_state, log_api_call
        )
        
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        state = get_api_state(api)
        
        # Reset minute counter if >60s
        calls_this_minute = state["calls_this_minute"]
        if state["last_call_at"]:
            last = datetime.fromisoformat(state["last_call_at"])
            if (now - last).total_seconds() >= 60:
                calls_this_minute = 0
        
        upsert_api_state(
            api,
            calls_today=state["calls_today"] + 1,
            calls_this_minute=calls_this_minute + 1,
            last_call_at=now_str,
            total_calls_lifetime=state["total_calls_lifetime"] + 1,
            quota_used_today=state["quota_used_today"] + cost
        )
        
        log_api_call(api, cost_units=cost, success=True, response_code=200)

    def record_limit(self, api: str, retry_after: int = 60) -> None:
        """
        Record a 429 response.
        Sets cooldown.
        """
        from core.db.rate_limits_db import upsert_api_state, log_api_call
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        upsert_api_state(
            api,
            last_429_at=now_str,
            retry_after_seconds=retry_after
        )
        
        log_api_call(api, success=False, response_code=429)
        
        logger.warning(f"[rate] {api} 429 recorded. Retry after {retry_after}s")

    def time_until_available(self, api: str) -> int:
        """
        Seconds until next call allowed.
        Returns 0 if available now.
        """
        from core.db.rate_limits_db import get_api_state
        
        state = get_api_state(api)
        if not state["last_429_at"]:
            return 0
        
        now = datetime.now()
        last_429 = datetime.fromisoformat(state["last_429_at"])
        retry_after = state["retry_after_seconds"] or 60
        cooldown_until = last_429 + timedelta(seconds=retry_after)
        
        if now >= cooldown_until:
            return 0
        return int((cooldown_until - now).total_seconds())

    def get_status(self) -> list[dict]:
        """
        Current state of all tracked APIs.
        Used by /status command.
        """
        from core.db.rate_limits_db import get_all_api_states
        
        states = get_all_api_states()
        now = datetime.now()
        result = []
        
        for state in states:
            api = state["api_name"]
            limits = self.LIMITS.get(api, {})
            
            available = self.can_call(api)
            wait = self.time_until_available(api)
            daily_limit = limits.get("units_per_day") or limits.get("requests_per_day")
            
            result.append({
                "api": api,
                "available": available,
                "wait_seconds": wait,
                "calls_today": state["calls_today"],
                "daily_limit": daily_limit,
                "quota_used": state["quota_used_today"],
                "last_429": state["last_429_at"],
                "total_calls": state["total_calls_lifetime"]
            })
        
        return result

    def _maybe_reset_daily(self, api: str, state: dict, now: datetime) -> None:
        """Reset daily counters at midnight."""
        from core.db.rate_limits_db import upsert_api_state
        
        today = now.strftime("%Y-%m-%d")
        reset_at = state.get("day_reset_at", "")
        
        if not reset_at or not reset_at.startswith(today):
            upsert_api_state(
                api,
                calls_today=0,
                quota_used_today=0,
                day_reset_at=now.strftime("%Y-%m-%d %H:%M:%S")
            )


# ─── Singleton ────────────────────────────
rate_limits = RateLimitManager()
