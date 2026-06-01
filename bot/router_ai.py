"""Intent classifier — routes user messages to focused tool subsets.

ADR-036: Ollama/gemma3:4b classifies intent. Agent gets 3-7 focused tools
instead of 30+. Plain text messages only; slash commands bypass this entirely.
"""

import json
import logging
import os
import yaml
from pathlib import Path

from api.local.ollama_api import ollama_api

logger = logging.getLogger("privy.router")

_routes_path = Path(__file__).parent.parent / "config" / "routes.yaml"
with open(_routes_path) as _f:
    ROUTES: dict = yaml.safe_load(_f).get("routes", {})

VALID_ROUTES: set[str] = set(ROUTES.keys())

# Classification model and timeout (separate from chat model for CPU optimization)
CLASSIFY_MODEL = os.environ.get("OLLAMA_CLASSIFY_MODEL", "qwen2.5:1.5b")
CLASSIFY_TIMEOUT = float(os.environ.get("OLLAMA_CLASSIFY_TIMEOUT", "15.0"))

KEYWORD_ROUTE_MAP: dict[str, str] = {
    "email": "email",   "emails": "email",   "inbox": "email",   "mail": "email",
    "calendar": "calendar", "schedule": "calendar", "meeting": "calendar",
    "appointments": "calendar", "availability": "calendar",
    "voidrift": "voidrift", "voiddrift": "voidrift", "itch": "voidrift", "itch.io": "voidrift",
    "youtube": "youtube", "video": "youtube",   "channel": "youtube",
    "views": "youtube",  "subscribers": "youtube",
    "weather": "weather", "forecast": "weather",
    "blog": "blog", "wordpress": "blog",
    "goal": "goals",  "goals": "goals",  "task": "goals",  "tasks": "goals",
    "milestone": "goals", "focus": "goals",
    "steam": "steam",
    "reddit": "voidrift", "commit": "code", "commits": "code",
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


def _keyword_fallback(message: str) -> list[str]:
    """Keyword scan — safety net when Ollama returns 'chat' or is unavailable."""
    msg = message.lower()
    for keyword, route in KEYWORD_ROUTE_MAP.items():
        if keyword in msg:
            return [route]
    return ["chat"]


async def classify(message: str) -> list[str]:
    """Classify message to route names via three-layer fallback stack.

    Layer 1: Small model with short timeout (fast CPU classification)
    Layer 2: Keyword heuristic (instant, always works)
    Layer 3: Default to ["chat"] (safe, never crashes)
    """
    # Layer 1: small model, short timeout
    if ollama_api.enabled:
        try:
            raw = await ollama_api.classify(
                message,
                model=CLASSIFY_MODEL,
                timeout=CLASSIFY_TIMEOUT
            )
            routes = parse_routes(raw)
            if routes != ["chat"]:
                return routes  # got a real answer, done
        except Exception:
            pass  # fall through to keyword fallback

    # Layer 2: keyword heuristic
    routes = _keyword_fallback(message)
    if routes != ["chat"]:
        logger.info(f"[router_ai] keyword fallback → {routes}")
        return routes

    # Layer 3: default
    return ["chat"]


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
