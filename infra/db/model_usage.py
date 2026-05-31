"""Model usage tracking — request counting, rate limit memory, cost tracking."""

from datetime import datetime, timedelta
from infra.db.schema import _exec
from infra.db.budget_tracking import record_cost as record_budget_cost


def record_model_call(
    model_id: str,
    provider: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    success: bool = True,
    error_code: int = None,
    latency_ms: int = None
) -> None:
    """
    Record a model API call to the usage table.

    Args:
        model_id: Model identifier (e.g., "deepseek/deepseek-v4-flash:free")
        provider: Provider name (e.g., "openrouter", "ollama", "groq")
        tokens_in: Input tokens used
        tokens_out: Output tokens generated
        cost_usd: Cost in USD
        success: Whether the call succeeded
        error_code: HTTP error code if failed (429, 404, etc.)
        latency_ms: Request latency in milliseconds
    """
    _exec(
        """INSERT INTO model_usage 
           (model_id, provider, tokens_in, tokens_out, cost_usd, success, error_code, latency_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            model_id,
            provider,
            tokens_in,
            tokens_out,
            cost_usd,
            1 if success else 0,
            error_code,
            latency_ms
        ),
        commit=True
    )
    
    # Track budget for paid providers with cost
    if success and cost_usd > 0 and provider != "ollama":
        from bot.model_manager import DAILY_PAID_CAPS
        daily_cap = DAILY_PAID_CAPS.get(provider)
        if daily_cap:
            try:
                record_budget_cost(provider, model_id, cost_usd, daily_cap)
            except Exception:
                pass  # Budget tracking is non-critical


def count_model_calls(model_id: str = None, provider: str = None, minutes: int = None, hours: int = None) -> int:
    """
    Count model calls within a time window.

    Args:
        model_id: Optional model ID filter
        provider: Optional provider filter
        minutes: Look back this many minutes
        hours: Look back this many hours

    Returns:
        Number of calls in the time window
    """
    conditions = []
    params = []

    if model_id:
        conditions.append("model_id = ?")
        params.append(model_id)

    if provider:
        conditions.append("provider = ?")
        params.append(provider)

    if minutes:
        conditions.append("called_at >= datetime('now', ? || ' minutes')")
        params.append(f"-{minutes}")
    elif hours:
        conditions.append("called_at >= datetime('now', ? || ' hours')")
        params.append(f"-{hours}")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    row = _exec(
        f"SELECT COUNT(*) as count FROM model_usage WHERE {where_clause}",
        params
    ).fetchone()

    return row["count"] if row else 0


def count_model_calls_minute(model_id: str = None) -> int:
    """
    Count model calls in the last 60 seconds.

    Args:
        model_id: Optional model ID filter

    Returns:
        Number of calls in the last 60 seconds
    """
    return count_model_calls(model_id=model_id, minutes=1)


def count_model_errors(model_id: str = None, error_code: int = None, minutes: int = None, hours: int = None) -> int:
    """
    Count model errors within a time window.

    Args:
        model_id: Optional model ID filter
        error_code: Optional error code filter (e.g., 429)
        minutes: Look back this many minutes
        hours: Look back this many hours

    Returns:
        Number of errors in the time window
    """
    conditions = ["success = 0"]
    params = []

    if model_id:
        conditions.append("model_id = ?")
        params.append(model_id)

    if error_code:
        conditions.append("error_code = ?")
        params.append(error_code)

    if minutes:
        conditions.append("called_at >= datetime('now', ? || ' minutes')")
        params.append(f"-{minutes}")
    elif hours:
        conditions.append("called_at >= datetime('now', ? || ' hours')")
        params.append(f"-{hours}")

    where_clause = " AND ".join(conditions)

    row = _exec(
        f"SELECT COUNT(*) as count FROM model_usage WHERE {where_clause}",
        params
    ).fetchone()

    return row["count"] if row else 0


def get_last_error_time(model_id: str, error_code: int = None) -> datetime | None:
    """
    Get the timestamp of the last error for a model.

    Args:
        model_id: Model ID
        error_code: Optional error code filter

    Returns:
        Datetime of last error, or None if no errors
    """
    conditions = ["success = 0", "model_id = ?"]
    params = [model_id]

    if error_code:
        conditions.append("error_code = ?")
        params.append(error_code)

    where_clause = " AND ".join(conditions)

    row = _exec(
        f"SELECT called_at FROM model_usage WHERE {where_clause} ORDER BY called_at DESC LIMIT 1",
        params
    ).fetchone()

    if row and row["called_at"]:
        return datetime.strptime(row["called_at"], "%Y-%m-%d %H:%M:%S")
    return None


def get_daily_cost(provider: str = None, days: int = 1) -> float:
    """
    Get total cost in USD for a time window.

    Args:
        provider: Optional provider filter
        days: Look back this many days

    Returns:
        Total cost in USD
    """
    conditions = []
    params = []

    if provider:
        conditions.append("provider = ?")
        params.append(provider)

    conditions.append("called_at >= datetime('now', ? || ' days')")
    params.append(f"-{days}")

    where_clause = " AND ".join(conditions)

    row = _exec(
        f"SELECT SUM(cost_usd) as total FROM model_usage WHERE {where_clause}",
        params
    ).fetchone()

    return row["total"] if row and row["total"] else 0.0


def get_model_stats(model_id: str, hours: int = 24) -> dict:
    """
    Get usage statistics for a specific model.

    Args:
        model_id: Model ID
        hours: Look back this many hours

    Returns:
        Dict with call count, error count, avg latency, total cost
    """
    row = _exec(
        """SELECT 
           COUNT(*) as calls,
           SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors,
           AVG(latency_ms) as avg_latency,
           SUM(cost_usd) as total_cost
           FROM model_usage
           WHERE model_id = ? AND called_at >= datetime('now', ? || ' hours')""",
        (model_id, f"-{hours}")
    ).fetchone()

    if row:
        return {
            "calls": row["calls"] or 0,
            "errors": row["errors"] or 0,
            "avg_latency": row["avg_latency"] or 0,
            "total_cost": row["total_cost"] or 0.0
        }
    return {"calls": 0, "errors": 0, "avg_latency": 0, "total_cost": 0.0}
