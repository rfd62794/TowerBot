"""YouTube tool — fetch channel performance data."""

from datetime import datetime, timedelta


def get_channel_summary(days: int = 7) -> dict:
    """
    Get YouTube channel performance for last N days.

    Args:
        days: Number of days to look back (default: 7)

    Returns:
        Dict with views, watch_time, subscribers, and top_series data.

    Note:
        This is a stub implementation. To integrate with ContentPipeline:
        1. Import the actual ContentPipeline client function
        2. Call it with start/end dates
        3. Return the results in this format

    Example integration:
        from content_pipeline_client import get_summary
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return get_summary(start, end)
    """
    # Stub implementation — replace with actual ContentPipeline call
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # TODO: Replace with actual ContentPipeline integration
    # from content_pipeline_client import get_summary
    # return get_summary(start, end)

    # Mock data for testing
    return {
        "status": "success",
        "period": f"{start} to {end}",
        "views": 1529,
        "watch_time_minutes": 128,
        "subscribers_gained": 7,
        "top_series": "EIC",
        "notes": "EIC performing best. Dune unproven — check by June 7.",
    }
