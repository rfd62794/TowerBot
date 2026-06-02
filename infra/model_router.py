"""
Model router — routes LLM calls by role, free first, budget-aware.
Tracks spend via existing budget_tracker infrastructure.
"""
import logging
import os
from pathlib import Path
from typing import Callable
import yaml

logger = logging.getLogger(__name__)

_REGISTRY = None
_REGISTRY_PATH = Path(__file__).parent.parent / "config" / "model_registry.yaml"


def _load_registry() -> dict:
    global _REGISTRY
    if _REGISTRY is None:
        with open(_REGISTRY_PATH, "r") as f:
            _REGISTRY = yaml.safe_load(f)
    return _REGISTRY


def get_model_for_role(role: str) -> list[dict]:
    """Return ordered list of model configs for a role."""
    registry = _load_registry()
    model_keys = registry["role_routing"].get(role, ["gemini_flash"])
    models = registry["models"]
    return [
        {"key": k, **models[k]}
        for k in model_keys
        if k in models
    ]


def _get_daily_spent() -> float:
    """Get today's OpenRouter spend from budget tracker."""
    try:
        from infra.db.budget_tracking import get_daily_spent
        return get_daily_spent(provider="openrouter") or 0.0
    except Exception:
        return 0.0


def _record_spend(model_key: str, cost_usd: float) -> None:
    """Record model call cost to budget tracker."""
    try:
        from infra.db.budget_tracking import record_cost
        record_cost(
            provider="openrouter",
            model=model_key,
            cost_usd=cost_usd
        )
    except Exception as e:
        logger.warning(f"Failed to record spend: {e}")


def _check_budget(model_config: dict) -> bool:
    """
    Return True if this model call is permitted within budget.
    Free models always permitted.
    Paid models blocked if daily cap reached.
    """
    if model_config.get("tier") == "free":
        return True
    registry = _load_registry()
    cap = registry["budget"]["daily_hard_cap_usd"]
    spent = _get_daily_spent()
    if spent >= cap:
        logger.warning(
            f"Daily budget cap ${cap} reached (spent ${spent:.4f}). "
            f"Blocking paid model {model_config['model_id']}"
        )
        return False
    return True


def _maybe_warn_budget() -> None:
    """Send Telegram warning if spend crosses warning threshold."""
    try:
        registry = _load_registry()
        warning = registry["budget"]["daily_warning_usd"]
        spent = _get_daily_spent()
        if spent >= warning:
            from infra.db.budget_tracking import get_warning_sent_today
            from infra.db.budget_tracking import mark_warning_sent
            if not get_warning_sent_today():
                # Import lazily to avoid circular deps
                logger.warning(
                    f"Budget warning: ${spent:.4f} spent today "
                    f"(warning threshold ${warning})"
                )
                mark_warning_sent()
    except Exception:
        pass


def route(role: str, prompt: str, **kwargs) -> dict:
    """
    Route an LLM call to the best available model for the role.

    Tries models in order:
    1. Free models first
    2. Near-free if free exhausted
    3. Paid only if budget permits and lower tiers failed

    Uses provider-specific call functions (Groq, Google, OpenRouter) based on model config.

    Returns dict with keys: result (str), model_used (str), cost_usd (float)
    Raises RuntimeError if all models fail.
    """
    from bot.model_helpers import get_call_fn
    
    candidates = get_model_for_role(role)

    if not candidates:
        raise RuntimeError(f"No models configured for role: {role}")

    last_error = None
    for model_config in candidates:
        model_key = model_config["key"]
        model_id = model_config["model_id"]
        provider = model_config["provider"]

        if not _check_budget(model_config):
            logger.info(f"Skipping {model_key} — budget cap reached")
            continue

        try:
            # Get provider-specific call function
            call_fn = get_call_fn(provider)
            
            result = call_fn(
                model=model_id,
                provider=provider,
                prompt=prompt,
                **kwargs
            )

            # Estimate cost (rough — real cost from response headers if available)
            est_tokens = len(prompt.split()) * 1.3
            cost = (est_tokens / 1000) * model_config.get(
                "cost_per_1k_input", 0.0
            )
            if cost > 0:
                _record_spend(model_key, cost)
                _maybe_warn_budget()

            logger.info(f"Role '{role}' served by {model_key} (provider: {provider})")
            return {
                "result": result,
                "model_used": model_key,
                "model_id": model_id,
                "cost_usd": cost
            }

        except Exception as e:
            logger.warning(f"Model {model_key} failed for role {role}: {e}")
            last_error = e
            continue

    raise RuntimeError(
        f"All models failed for role '{role}'. Last error: {last_error}"
    )


def get_today_spend() -> dict:
    """Return today's spend summary for /status display."""
    registry = _load_registry()
    spent = _get_daily_spent()
    cap = registry["budget"]["daily_hard_cap_usd"]
    warning = registry["budget"]["daily_warning_usd"]
    return {
        "spent_usd": round(spent, 4),
        "cap_usd": cap,
        "remaining_usd": round(max(0.0, cap - spent), 4),
        "warning_usd": warning,
        "at_warning": spent >= warning,
        "at_cap": spent >= cap,
        "percent_used": round((spent / cap) * 100, 1) if cap > 0 else 0
    }
