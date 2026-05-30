"""Video-level YouTube tools."""

import hashlib
import json
from datetime import datetime, timedelta
from core.db import cache_tool_result, get_cached_tool_result
from tools.api.youtube_api import (
    query_video_report,
    query_retention_curve,
    get_channel_uploads_playlist_id,
    get_playlist_items,
    get_video_statistics,
)


def _hash_params(params: dict) -> str:
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()


def get_top_videos(days: int = 7, limit: int = 10) -> dict:
    """
    Get top videos by views for last N days.

    Args:
        days: Number of days to look back (default: 7)
        limit: Maximum number of videos to return (default: 10)

    Returns:
        Dict with list of top videos and their stats.
    """
    params = {"days": days, "limit": limit}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_top_videos", params_hash)
    if cached:
        return cached

    try:
        playlist_response = get_channel_uploads_playlist_id()
        if "error" in playlist_response:
            return playlist_response

        playlist_data = playlist_response["raw"]
        if not playlist_data.get("items"):
            return {"error": "No channel data found"}

        uploads_playlist_id = playlist_data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        items_response = get_playlist_items(uploads_playlist_id, max_results=limit)
        if "error" in items_response:
            return items_response

        items_data = items_response["raw"]
        video_ids = [item["contentDetails"]["videoId"] for item in items_data.get("items", [])]

        if not video_ids:
            return {
                "videos": [],
                "period_days": days,
            }

        stats_response = get_video_statistics(video_ids)
        if "error" in stats_response:
            return stats_response

        stats = stats_response["raw"]
        videos = []
        for video in stats.get("items", []):
            snippet = video.get("snippet", {})
            videos.append({
                "video_id": video["id"],
                "title": snippet.get("title", "Unknown"),
                "published_at": snippet.get("publishedAt", ""),
                "views": int(video["statistics"].get("viewCount", 0)),
                "watch_time_minutes": 0,
            })

        videos.sort(key=lambda x: x["views"], reverse=True)

        result = {
            "videos": videos[:limit],
            "period_days": days,
        }

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
    params = {"video_id": video_id, "days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_video_analytics", params_hash)
    if cached:
        return cached

    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_video_report(video_id, start, end, "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage", dimensions="video")
        if "error" in api_response:
            return api_response

        response = api_response.get("raw")
        if response is None:
            return {"error": "No analytics data", "video_id": video_id}

        rows = response.get("rows", [])
        if not rows:
            return {"error": "No data returned for this video", "video_id": video_id}

        row = rows[0]
        result = {
            "video_id": video_id,
            "views": int(row[1]),
            "watch_time_minutes": float(row[2]),
            "avg_view_duration_seconds": float(row[3]),
            "avg_view_percentage": float(row[4]),
            "period_days": days,
        }

        cache_tool_result("get_video_analytics", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_retention_curve(video_id: str, days: int = 28) -> dict:
    """
    Get retention curve for a specific video.

    Args:
        video_id: YouTube video ID
        days: Number of days to look back (default: 28)

    Returns:
        Dict with retention curve data and drop-off point
    """
    params = {"video_id": video_id, "days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_retention_curve", params_hash)
    if cached:
        return cached

    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_retention_curve(video_id, start, end)
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [])

        curve = []
        drop_off_point = None

        for row in rows:
            ratio = float(row[0])
            watch_ratio = float(row[1])
            relative_retention = float(row[2]) if len(row) > 2 else 0.0

            curve.append({
                "ratio": ratio,
                "watch_ratio": watch_ratio,
                "relative_retention": relative_retention,
            })

            if drop_off_point is None and watch_ratio < 0.5:
                drop_off_point = ratio

        result = {
            "video_id": video_id,
            "curve": curve,
            "drop_off_point": drop_off_point,
            "period_days": days,
        }

        cache_tool_result("get_retention_curve", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}
