"""Model Manager — dynamic free-model discovery + throttle tracking.

Queries OpenRouter's /models API for free, tool-capable models, caches the
list for 24h, and tracks 429 cooldowns per model in SQLite. Sync HTTP only.
Single responsibility: discover models and track throttles.
"""

import os
import asyncio
import logging

import httpx

from infra.db import (
    record_throttle,
    record_success,
    get_throttled_models,
    cache_model_list,
    get_cached_model_list,
    get_model_status_all,
)

logger = logging.getLogger("privy.models")

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Daily paid API caps by mode
DAILY_PAID_CAPS = {
    "dev": 1.00,      # testing — relaxed
    "production": 0.25,  # overnight steady state
}

# Current mode from env, defaults to production
PRIVYBOT_MODE = os.getenv("PRIVYBOT_MODE", "production")

# Known model limits for rate limit avoidance
# Local models have None limits (no rate limiting)
MODEL_LIMITS = {
    # OpenRouter free — 200/day per model
    "deepseek/deepseek-v4-flash:free": {"rpm": 20, "rpd": 200},
    "google/gemma-4-31b-it:free": {"rpm": 20, "rpd": 200},
    "openai/gpt-oss-120b:free": {"rpm": 20, "rpd": 200},
    "moonshotai/kimi-k2.6:free": {"rpm": 20, "rpd": 200},
    "nex-agi/deepseek-v3.1-nex-n1:free": {"rpm": 20, "rpd": 200},
    "qwen/qwen3-coder:free": {"rpm": 20, "rpd": 200},
    "openrouter/free": {"rpm": 20, "rpd": 200},
    
    # Groq free
    "groq/llama-3.3-70b-versatile": {"rpm": 30, "rpd": 14400},
    
    # Google AI Studio free
    "google/gemini-2.0-flash": {"rpm": 15, "rpd": 1500},
    
    # Ollama local — no limits
    "ollama": {"rpm": None, "rpd": None},
}

# Known tool-capable free models — fallback only if live discovery fails.
# deepseek/deepseek-v4-flash:free removed — 404 on OpenRouter (model gone)
SEED_FREE_MODELS = [
    "openrouter/free",  # primary — auto-routes across all free models with tool calling
    "openai/gpt-oss-120b:free",  # OpenAI open-weight, 117B
    "moonshotai/kimi-k2.6:free",  # solid tool calling
    "google/gemma-4-31b-it:free",  # 256K context, function calling
    "nex-agi/deepseek-v3.1-nex-n1:free",  # agent tasks, tool use
    "qwen/qwen3-coder:free",  # 1M context, coding
]

# Models with tool-calling format incompatibilities (leak raw tool-call text)
# Populated after test_models.py validation
TOOL_INCOMPATIBLE = {
    "openrouter/owl-alpha",  # Leaks raw longcat XML tool calls
    "z-ai/glm-4.5-air:free",  # Known incompatibility
    "poolside/laguna-xs.2:free",  # Leaks raw XML tool calls
    "poolside/laguna-m.1:free",  # Leaks raw XML tool calls
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",  # Leaks raw XML tool calls
    "nvidia/nemotron-3-super-120b-a12b:free",  # Leaks raw XML tool calls
}


def fetch_free_tool_models() -> list:
    """Return free, tool-capable model ids. Cached 1h via OpenRouterAPIHandler; seeds on failure."""
    cached = get_cached_model_list()
    if cached:
        return cached

    try:
        from api.web.openrouter_api import openrouter_api
        result = openrouter_api.get_free_models()
        if not result:
            result = SEED_FREE_MODELS
        cache_model_list(result)
        return result
    except Exception as e:
        logger.error("fetch_free_tool_models failed: %s", e)
        return SEED_FREE_MODELS


def discover_free_models() -> dict:
    """
    Query OpenRouter API for current free models with tool calling support.
    Returns dict with count and list of model IDs.
    """
    try:
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
            "HTTP-Referer": "https://github.com/rfd62794/PrivyBot",
        }
        resp = httpx.get(f"{OPENROUTER_MODELS_URL}?supported_parameters=tools", headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        result = []
        for model in data:
            pricing = model.get("pricing", {})
            is_free = pricing.get("prompt") == "0" and pricing.get("completion") == "0"
            has_tools = "tools" in model.get("supported_parameters", [])
            if is_free and has_tools:
                result.append(model["id"])

        return {
            "ok": True,
            "count": len(result),
            "models": result
        }
    except Exception as e:
        logger.error("discover_free_models failed: %s", e)
        return {
            "ok": False,
            "error": str(e),
            "count": 0,
            "models": []
        }


def get_daily_cap() -> float:
    """Get current daily paid cap based on PRIVYBOT_MODE."""
    return DAILY_PAID_CAPS.get(PRIVYBOT_MODE, DAILY_PAID_CAPS["production"])


def can_use_paid_model() -> bool:
    """Check if we're under the daily paid cap for current mode."""
    from infra.db.rate_limits_db import get_api_state
    
    # Get today's cost from OpenRouter API state
    state = get_api_state("openrouter")
    daily_cap = get_daily_cap()
    
    # quota_used_today is in USD
    today_cost = state.get("quota_used_today", 0.0)
    
    return today_cost < daily_cap


def should_skip_model(model_id: str) -> tuple[bool, str]:
    """
    Check if a model should be skipped based on rate limits and recent errors.
    
    Args:
        model_id: Model identifier
        
    Returns:
        Tuple of (should_skip, reason)
    """
    from datetime import datetime, timedelta
    from infra.db.model_usage import count_model_calls, count_model_errors, get_last_error_time, count_model_calls_minute
    from infra.db.budget_tracking import get_budget_status
    
    # Ollama local models never skip
    if model_id == "ollama" or model_id.startswith("ollama/"):
        return False, "local"
    
    limits = MODEL_LIMITS.get(model_id, {})
    
    # Local models never skip
    if limits.get("rpm") is None:
        return False, "local"
    
    # Check budget for paid providers
    provider = limits.get("provider", "openrouter")
    if provider in DAILY_PAID_CAPS:
        daily_cap = DAILY_PAID_CAPS[provider]
        try:
            budget = get_budget_status(provider, model_id, daily_cap)
            if budget["over_budget"]:
                return True, f"budget_exceeded (${budget['daily_spent_usd']:.2f}/${daily_cap:.2f})"
            if budget["percent_used"] > 90:
                return True, f"budget_warning ({budget['percent_used']:.0f}% used)"
        except Exception:
            pass  # Budget tracking failure shouldn't block
    
    # Check daily usage — skip if within 5% of limit
    rpd = limits.get("rpd", 200)
    used_today = count_model_calls(model_id, hours=24)
    if used_today >= rpd * 0.95:
        return True, f"daily_limit ({used_today}/{rpd})"
    
    # Check recent 429s — exponential backoff
    recent_429s = count_model_errors(model_id, error_code=429, minutes=60)
    if recent_429s > 0:
        last_429 = get_last_error_time(model_id, error_code=429)
        if last_429:
            backoff_seconds = min(300, 30 * (2 ** recent_429s))
            if datetime.utcnow() < last_429 + timedelta(seconds=backoff_seconds):
                return True, f"backoff ({backoff_seconds}s, {recent_429s} hits)"
    
    # Check RPM — skip if >80% of limit used in last minute
    rpm = limits.get("rpm", 20)
    used_minute = count_model_calls_minute(model_id)
    if used_minute >= rpm * 0.8:
        return True, f"rpm_limit ({used_minute}/{rpm})"
    
    return False, "ok"


def get_available_model() -> str | None:
    """
    Best available model with provider priority:
    1. Ollama (if enabled and healthy)
    2. openrouter/free (auto-routes across all free models)
    3. SEED_FREE_MODELS (individual free models)
    4. None (all rate-limited)
    """
    from api.local.ollama_api import ollama_api
    
    # Priority 0: Ollama local
    ollama_healthy = ollama_api.health_check()
    logger.info("Checking Ollama: enabled=%s health=%s", ollama_api.enabled, ollama_healthy)
    if ollama_healthy:
        return f"ollama/{ollama_api.model}"
    elif ollama_api.enabled and not ollama_api._starting:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(ollama_api.ensure_running())
            logger.info("[Ollama] Recovery started — routing to OpenRouter")
        except RuntimeError:
            pass  # no running loop (test context) — do not create the coroutine
    
    # Priority 1: openrouter/free
    throttled = set(get_throttled_models())
    if "openrouter/free" not in throttled and "openrouter/free" not in TOOL_INCOMPATIBLE:
        should_skip, skip_reason = should_skip_model("openrouter/free")
        if not should_skip:
            return "openrouter/free"
    
    # Priority 2: SEED_FREE_MODELS
    for model_id in SEED_FREE_MODELS:
        if model_id == "openrouter/free":
            continue  # Already checked
        if model_id not in throttled and model_id not in TOOL_INCOMPATIBLE:
            should_skip, skip_reason = should_skip_model(model_id)
            if not should_skip:
                return model_id

    # Priority 3: cheapest paid model (only when free pool exhausted and under daily cap)
    paid_model = os.getenv("OPENROUTER_PAID_MODEL")
    if paid_model and can_use_paid_model():
        logger.info("[model] All free models exhausted — falling back to paid: %s", paid_model)
        return paid_model

    return None


def handle_429(model_id: str, retry_after: float = 60.0) -> None:
    record_throttle(model_id, retry_after)


def handle_success(model_id: str) -> None:
    record_success(model_id)


def get_status_report() -> str:
    """Human-readable model status for the /models command."""
    rows = get_model_status_all()
    models = fetch_free_tool_models()
    throttled = set(get_throttled_models())

    lines = ["🤖 Model Status\n", f"Free tool-capable models: {len(models)}\n"]
    if not rows:
        lines.append("No throttle history yet.")
        return "\n".join(lines)

    for row in rows:
        status = "🔴 throttled" if row["model_id"] in throttled else "🟢 available"
        lines.append(
            f"{status} {row['model_id']}\n"
            f"  fails: {row['fail_count']} | "
            f"last success: {row['last_success'] or 'never'}"
        )
    return "\n".join(lines)
