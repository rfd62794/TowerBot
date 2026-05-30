"""Model Manager — dynamic free-model discovery + throttle tracking.

Queries OpenRouter's /models API for free, tool-capable models, caches the
list for 24h, and tracks 429 cooldowns per model in SQLite. Sync HTTP only.
Single responsibility: discover models and track throttles.
"""

import os
import logging

import httpx

from db import (
    record_throttle,
    record_success,
    get_throttled_models,
    cache_model_list,
    get_cached_model_list,
    get_model_status_all,
)

logger = logging.getLogger("privy.models")

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Known tool-capable free models, used only if the API call fails.
SEED_FREE_MODELS = [
    "deepseek/deepseek-v4-flash:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "moonshotai/kimi-k2.6:free",
]

# Models with tool-calling format incompatibilities (leak raw tool-call text)
TOOL_INCOMPATIBLE = {"openrouter/owl-alpha"}


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
        resp = httpx.get(OPENROUTER_MODELS_URL, headers=headers, timeout=10.0)
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
