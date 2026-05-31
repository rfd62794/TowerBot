"""Model Manager — dynamic free-model discovery + throttle tracking.

Queries OpenRouter's /models API for free, tool-capable models, caches the
list for 24h, and tracks 429 cooldowns per model in SQLite. Sync HTTP only.
Single responsibility: discover models and track throttles.
"""

import os
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
    "production": 0.10,  # overnight steady state
}

# Current mode from env, defaults to production
PRIVYBOT_MODE = os.getenv("PRIVYBOT_MODE", "production")

# Known tool-capable free models, used only if the API call fails.
# Prioritized by test results (PASS models from test_models.py)
SEED_FREE_MODELS = [
    "openrouter/free",  # primary — auto-routes across all free models with tool calling
    "deepseek/deepseek-v4-flash:free",  # 1M context, excellent
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
    """Return free, tool-capable model ids. Cached 24h; seeds on failure."""
    cached = get_cached_model_list()
    if cached:
        return cached

    try:
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
            "HTTP-Referer": "https://github.com/rfd62794/PrivyBot",
        }
        # Query for models that support tools
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


def get_available_model() -> str | None:
    """Best available free model, skipping those still in 429 cooldown or tool-incompatible."""
    throttled = set(get_throttled_models())
    for model_id in fetch_free_tool_models():
        if model_id not in throttled and model_id not in TOOL_INCOMPATIBLE:
            return model_id
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
