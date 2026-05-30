"""tools/api/_base.py

Shared pattern for all API calls.
cached_api_call() is the single wrapper every API function will use in Phase 2.

Phase 1: Define the pattern only.
Phase 2: Each API file adopts it.
"""

import json
import hashlib
import time
import logging
from typing import Callable

logger = logging.getLogger("privy.api.base")


def make_params_hash(*args, **kwargs) -> str:
    """
    Deterministic hash from call parameters.
    Used as params_hash in cache lookups.
    """
    key = json.dumps({"args": list(args), "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(key.encode()).hexdigest()


def cached_api_call(
    tool_name: str,
    params_hash: str,
    live_fn: Callable,
    ttl_seconds: int,
    stale_ok: bool = True,
) -> dict:
    """
    Standard wrapper for all API calls.

    Behavior:
    1. Check cache — fresh hit → return immediately
       (no network call, no staleness flag)
    2. Try live_fn() — success → cache + return
       (fresh data, no staleness flag)
    3. live_fn() raises exception:
       if stale_ok: try get_stale_cached_result()
         → return with _stale=True metadata
       else: return {"error": str(e), "_live_failed": True}

    All returned dicts have consistent shape:
      {"_stale": False, ...data...}     fresh
      {"_stale": True,                  stale
       "_cached_at": "...",
       "_age_minutes": N, ...data...}
      {"error": "...",                  failed
       "_live_failed": True}

    Args:
      tool_name: cache namespace key
      params_hash: cache lookup key
      live_fn: zero-arg callable returning dict
      ttl_seconds: cache TTL for fresh results (converted to hours internally)
      stale_ok: whether to fall back to stale data on live failure
    """
    from core.db.cache import (
        get_cached_tool_result,
        cache_tool_result,
        get_stale_cached_result,
    )

    # Step 1 — fresh cache hit
    cached = get_cached_tool_result(tool_name, params_hash)
    if cached is not None:
        cached["_stale"] = False
        return cached

    # Step 2 — live call
    start = time.time()
    try:
        result = live_fn()
        duration_ms = int((time.time() - start) * 1000)

        if not isinstance(result, dict):
            result = {"value": result}

        result["_stale"] = False

        # Convert ttl_seconds to ttl_hours for cache_tool_result
        ttl_hours = ttl_seconds / 3600
        cache_tool_result(tool_name, params_hash, result, ttl_hours)

        logger.debug(f"[API] {tool_name} live ({duration_ms}ms)")

        return result

    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        logger.warning(f"[API] {tool_name} live failed: {e}")

        # Step 3 — stale fallback
        if stale_ok:
            stale = get_stale_cached_result(tool_name, params_hash)
            if stale is not None:
                logger.info(
                    f"[API] {tool_name} serving stale ({stale.get('_age_minutes', '?')}min)"
                )
                return stale

        # Step 4 — total failure
        return {"error": str(e), "_live_failed": True, "_stale": False}


def stale_notice(result: dict) -> str | None:
    """
    Returns human-readable staleness notice or None if data is fresh.

    Used by tool functions to add stale_notice field to their return dicts.
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
