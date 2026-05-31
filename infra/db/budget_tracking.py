"""Budget tracking database functions."""

from datetime import datetime, timedelta
from infra.db.schema import _exec


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
           AND date(reset_at) = date('now', 'localtime')
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


def record_cost(provider: str, model_id: str, cost_usd: float, daily_cap_usd: float) -> dict:
    """
    Record a cost and update budget tracking.
    
    Args:
        provider: Provider name
        model_id: Model identifier
        cost_usd: Cost in USD
        daily_cap_usd: Daily budget cap in USD
        
    Returns:
        Dict with updated daily_spent_usd, daily_remaining_usd, over_budget flag
    """
    budget = get_or_create_budget(provider, model_id, daily_cap_usd)
    
    new_spent = budget["daily_spent_usd"] + cost_usd
    new_remaining = budget["daily_remaining_usd"] - cost_usd
    
    # Update the budget entry for today
    _exec(
        """UPDATE budget_tracking 
           SET daily_spent_usd = ?, daily_remaining_usd = ?
           WHERE provider = ? AND model_id = ? 
           AND date(reset_at) = date('now', 'localtime')""",
        (new_spent, new_remaining, provider, model_id),
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
