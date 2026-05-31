"""Intent classifier — routes user messages to focused tool subsets.

ADR-036: Ollama/gemma3:4b classifies intent. Agent gets 3-7 focused tools
instead of 30+. Plain text messages only; slash commands bypass this entirely.
"""

import json
import yaml
from pathlib import Path

from api.local.ollama_api import ollama_api

_routes_path = Path(__file__).parent.parent / "config" / "routes.yaml"
with open(_routes_path) as _f:
    ROUTES: dict = yaml.safe_load(_f).get("routes", {})

VALID_ROUTES: set[str] = set(ROUTES.keys())

DATA_SIGNALS = {
    "should", "what about", "how is", "update", "status",
    "today", "this week", "focus", "what's next", "check",
}


def parse_routes(raw: str) -> list[str]:
    """Parse raw Ollama JSON. Never raises. Always returns a valid list."""
    try:
        parsed = json.loads(raw.strip())
        routes = parsed.get("routes", [])
        valid = [r for r in routes if r in VALID_ROUTES]
        return valid if valid else ["chat"]
    except Exception:
        return ["chat"]


def _has_data_signal(message: str) -> bool:
    return any(sig in message.lower() for sig in DATA_SIGNALS)


async def classify(message: str) -> list[str]:
    """Classify message → route names via Ollama.

    Falls back to ["chat"] if Ollama is disabled or unavailable.
    Escalates ["chat"] to ["goals"] when message contains data signals.
    """
    if not ollama_api.enabled:
        return ["chat"]
    raw = await ollama_api.classify(message)
    routes = parse_routes(raw)
    if routes == ["chat"] and _has_data_signal(message):
        return ["goals"]
    return routes


def get_tools_for_routes(routes: list[str]) -> list[str]:
    """Merged, deduplicated tool list for the given routes."""
    seen: set[str] = set()
    tools: list[str] = []
    for route in routes:
        for tool in ROUTES.get(route, {}).get("tools") or []:
            if tool not in seen:
                tools.append(tool)
                seen.add(tool)
    return tools


def get_model_for_routes(routes: list[str]) -> str:
    """Target model for the given routes. First non-Ollama model wins.

    If all routes point to Ollama (chat-only), return the Ollama model string
    so the caller can route directly without touching OpenRouter.
    """
    for route in routes:
        model = ROUTES.get(route, {}).get("model", "")
        if model and model != "ollama/gemma3:4b":
            return model
    return ROUTES.get(routes[0] if routes else "chat", {}).get(
        "model", "openrouter/free"
    )
