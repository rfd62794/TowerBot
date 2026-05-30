"""YouTube tool — fetch channel performance data via YouTube Analytics API."""

import hashlib
import json
from datetime import datetime, timedelta
from core.db import cache_tool_result, get_cached_tool_result
from tools.api.youtube_api import query_channel_report, query_video_report


def _hash_params(params: dict) -> str:
    """Generate hash for cache key."""
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()


def get_channel_summary(days: int = 7) -> dict:
    """
    Get YouTube channel performance for last N days.

    Args:
        days: Number of days to look back (default: 7)

    Returns:
        Dict with views, watch_time, subscribers, and date range.
    """
    # Check cache
    params = {"days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_channel_summary", params_hash)
    if cached:
        return cached

    # Fetch fresh data
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_channel_report(start, end, "views,estimatedMinutesWatched,subscribersGained")
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [[0, 0, 0]])
        if not rows:
            return {"error": "No data returned from YouTube Analytics"}

        row = rows[0]
        result = {
            "views": int(row[0]),
            "watch_time_minutes": float(row[1]),
            "subscribers_gained": int(row[2]),
            "start_date": start,
            "end_date": end,
            "period_days": days,
        }

        # Cache result (6 hour TTL)
        cache_tool_result("get_channel_summary", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_channel_summary_range(start_date: str, end_date: str) -> dict:
    """
    Get YouTube channel performance for a specific date range.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Dict with views, watch_time, subscribers, and date range.
    """
    try:
        api_response = query_channel_report(start_date, end_date, "views,estimatedMinutesWatched,subscribersGained")
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [[0, 0, 0]])
        if not rows:
            return {"error": "No data returned from YouTube Analytics"}

        row = rows[0]
        return {
            "views": int(row[0]),
            "watch_time_minutes": float(row[1]),
            "subscribers_gained": int(row[2]),
            "start_date": start_date,
            "end_date": end_date,
        }
    except Exception as e:
        return {"error": str(e)}


def get_top_videos(days: int = 7, limit: int = 10) -> dict:
    """
    Get top videos by views for last N days.

    Args:
        days: Number of days to look back (default: 7)
        limit: Maximum number of videos to return (default: 10)

    Returns:
        Dict with list of top videos and their stats.
    """
    # Check cache
    params = {"days": days, "limit": limit}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_top_videos", params_hash)
    if cached:
        return cached

    # Fetch fresh data
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_video_report(None, start, end, "views,estimatedMinutesWatched", dimensions="video")
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [])
        videos = []
        for row in rows:
            videos.append({
                "video_id": row[0],
                "views": int(row[1]),
                "watch_time_minutes": float(row[2]),
            })

        result = {
            "videos": videos,
            "period_days": days,
        }

        # Cache result (6 hour TTL)
        cache_tool_result("get_top_videos", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_video_analytics(video_id: str, days: int = 28) -> dict:
    """
    Get detailed performance metrics for a specific YouTube video.

    Args:
        video_id: YouTube video ID
        days: Number of days to look back (default: 28)

    Returns:
        Dict with detailed video metrics
    """
    # Check cache
    params = {"video_id": video_id, "days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_video_analytics", params_hash)
    if cached:
        return cached

    # Fetch fresh data
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_video_report(video_id, start, end, "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage", dimensions="video")
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [])
        if not rows:
            return {"error": "No data returned for this video"}

        row = rows[0]
        result = {
            "video_id": video_id,
            "views": int(row[1]),
            "watch_time_minutes": float(row[2]),
            "avg_view_duration_seconds": float(row[3]),
            "avg_view_percentage": float(row[4]),
            "period_days": days,
        }

        # Cache result (6 hour TTL)
        cache_tool_result("get_video_analytics", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}
