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

    # Fetch fresh data using YouTube Data API v3 (Analytics v2 doesn't support video-level queries)
    try:
        from tools.api.youtube_api import search_youtube, get_video_statistics

        # Search for videos in the channel
        search_response = search_youtube("", days, max_results=limit)
        if "error" in search_response:
            return search_response

        response = search_response["raw"]
        video_ids = [item["id"]["videoId"] for item in response.get("items", [])]

        if not video_ids:
            return {
                "videos": [],
                "period_days": days,
            }

        # Get statistics for each video
        stats_response = get_video_statistics(video_ids)
        if "error" in stats_response:
            return stats_response

        stats = stats_response["raw"]
        videos = []
        for video in stats.get("items", []):
            videos.append({
                "video_id": video["id"],
                "views": int(video["statistics"].get("viewCount", 0)),
                "watch_time_minutes": 0,  # YouTube Data API doesn't provide watch time
            })

        # Sort by views descending
        videos.sort(key=lambda x: x["views"], reverse=True)

        result = {
            "videos": videos[:limit],
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
