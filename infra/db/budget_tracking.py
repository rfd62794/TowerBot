"""Budget tracking database functions."""

import logging
from datetime import datetime, timedelta
from infra.db.schema import _exec

logger = logging.getLogger(__name__)


def get_or_create_budget(provider: str, model_id: str, daily_cap_usd: float) -> dict:
    """
    Get or create budget tracking entry for a provider/model.
    
    Args:
        provider: Provider name (e.g., "openrouter", "google")
        model_id: Model identifier
        daily_cap_usd: Daily budget cap in USD
        
    Returns:
        Dict with daily_spent_usd, daily_remaining_usd, reset_at
    """
    # Try to get existing budget entry for today
    today = datetime.now().strftime("%Y-%m-%d")
    row = _exec(
        """SELECT * FROM budget_tracking 
           WHERE provider = ? AND model_id = ? 
           AND date(recorded_at) = date('now', 'localtime')
           ORDER BY recorded_at DESC LIMIT 1""",
        (provider, model_id)
    ).fetchone()
    
    if row:
        budget = dict(row)
        # Check if reset time has passed
        reset_at = datetime.fromisoformat(budget["reset_at"])
        if datetime.now() >= reset_at:
            # Reset budget
            return _reset_budget(provider, model_id, daily_cap_usd)
        return {
            "daily_spent_usd": budget["daily_spent_usd"],
            "daily_remaining_usd": budget["daily_remaining_usd"],
            "reset_at": budget["reset_at"]
        }
    else:
        # Create new budget entry
        reset_at = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        _exec(
            """INSERT INTO budget_tracking 
               (provider, model_id, daily_cap_usd, daily_spent_usd, daily_remaining_usd, reset_at)
               VALUES (?, ?, ?, 0.0, ?, ?)""",
            (provider, model_id, daily_cap_usd, daily_cap_usd, reset_at),
            commit=True
        )
        return {
            "daily_spent_usd": 0.0,
            "daily_remaining_usd": daily_cap_usd,
            "reset_at": reset_at
        }


def _reset_budget(provider: str, model_id: str, daily_cap_usd: float) -> dict:
    """Reset daily budget for a provider/model."""
    reset_at = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    _exec(
        """INSERT INTO budget_tracking 
           (provider, model_id, daily_cap_usd, daily_spent_usd, daily_remaining_usd, reset_at)
           VALUES (?, ?, ?, 0.0, ?, ?)""",
        (provider, model_id, daily_cap_usd, daily_cap_usd, reset_at),
        commit=True
    )
    return {
        "daily_spent_usd": 0.0,
        "daily_remaining_usd": daily_cap_usd,
        "reset_at": reset_at
    }


def _load_cap_from_registry() -> float:
    """
    Load daily budget cap from model_registry.yaml.

    Returns:
        Daily hard cap in USD, or 0.25 as default if registry unavailable
    """
    try:
        import yaml
        from pathlib import Path
        registry_path = Path(__file__).parent.parent.parent / "config" / "model_registry.yaml"
        with open(registry_path, "r") as f:
            registry = yaml.safe_load(f)
        return registry.get("budget", {}).get("daily_hard_cap_usd", 0.25)
    except Exception:
        logger.warning("Failed to load cap from registry, using default 0.25")
        return 0.25


def record_cost(provider: str, model: str, cost_usd: float,
                daily_cap_usd: float = None) -> dict:
    """
    Record a cost and update budget tracking.

    Args:
        provider: Provider name
        model: Model identifier (note: parameter name changed from model_id to model)
        cost_usd: Cost in USD
        daily_cap_usd: Daily budget cap in USD (optional, loads from registry if None)

    Returns:
        Dict with updated daily_spent_usd, daily_remaining_usd, over_budget flag
    """
    if daily_cap_usd is None:
        daily_cap_usd = _load_cap_from_registry()

    budget = get_or_create_budget(provider, model, daily_cap_usd)

    new_spent = budget["daily_spent_usd"] + cost_usd
    new_remaining = budget["daily_remaining_usd"] - cost_usd

    # Update the budget entry for today
    _exec(
        """UPDATE budget_tracking
           SET daily_spent_usd = ?, daily_remaining_usd = ?
           WHERE provider = ? AND model_id = ?
           AND date(recorded_at) = date('now', 'localtime')""",
        (new_spent, new_remaining, provider, model),
        commit=True
    )

    return {
        "daily_spent_usd": new_spent,
        "daily_remaining_usd": new_remaining,
        "over_budget": new_remaining < 0
    }


def get_daily_spent(provider: str = None, model_id: str = None) -> float:
    """
    Get total daily spent, optionally filtered by provider/model.
    
    Args:
        provider: Optional provider filter
        model_id: Optional model filter
        
    Returns:
        Total spent in USD
    """
    today = datetime.now().strftime("%Y-%m-%d")
    
    if provider and model_id:
        row = _exec(
            """SELECT COALESCE(SUM(daily_spent_usd), 0) as total
               FROM budget_tracking
               WHERE provider = ? AND model_id = ?
               AND date(recorded_at) = date('now', 'localtime')""",
            (provider, model_id)
        ).fetchone()
    elif provider:
        row = _exec(
            """SELECT COALESCE(SUM(daily_spent_usd), 0) as total
               FROM budget_tracking
               WHERE provider = ?
               AND date(recorded_at) = date('now', 'localtime')""",
            (provider,)
        ).fetchone()
    else:
        row = _exec(
            """SELECT COALESCE(SUM(daily_spent_usd), 0) as total
               FROM budget_tracking
               WHERE date(recorded_at) = date('now', 'localtime')"""
        ).fetchone()
    
    return row["total"] if row else 0.0


def get_budget_status(provider: str, model_id: str, daily_cap_usd: float) -> dict:
    """
    Get current budget status for a provider/model.

    Args:
        provider: Provider name
        model_id: Model identifier
        daily_cap_usd: Daily budget cap in USD

    Returns:
        Dict with spent, remaining, percent_used, over_budget flag
    """
    budget = get_or_create_budget(provider, model_id, daily_cap_usd)
    percent_used = (budget["daily_spent_usd"] / daily_cap_usd * 100) if daily_cap_usd > 0 else 0

    return {
        "daily_spent_usd": budget["daily_spent_usd"],
        "daily_remaining_usd": budget["daily_remaining_usd"],
        "daily_cap_usd": daily_cap_usd,
        "percent_used": round(percent_used, 2),
        "over_budget": budget["daily_remaining_usd"] < 0,
        "reset_at": budget["reset_at"]
    }


def get_warning_sent_today() -> bool:
    """
    Check if a budget warning has been sent today.

    Returns:
        True if warning was sent today, False otherwise
    """
    today = datetime.now().strftime("%Y-%m-%d")
    row = _exec(
        """SELECT warning_sent FROM budget_tracking
           WHERE date(recorded_at) = date('now', 'localtime')
           AND warning_sent = 1
           LIMIT 1"""
    ).fetchone()
    return row is not None


def mark_warning_sent() -> None:
    """
    Mark that a budget warning has been sent today.
    Sets warning_sent flag on today's budget_tracking entries.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    _exec(
        """UPDATE budget_tracking
           SET warning_sent = 1
           WHERE date(recorded_at) = date('now', 'localtime')""",
        commit=True
    )
    logger.info("Budget warning flag set for today")
