"""YouTube tool — fetch channel performance data via YouTube Analytics API."""

import hashlib
import json
from datetime import datetime, timedelta
from core.db import cache_tool_result, get_cached_tool_result
from tools.api.youtube_api import (
    query_channel_report,
    query_video_report,
    query_traffic_sources,
    query_demographics,
    query_retention_curve,
    query_device_types,
    query_daily_views,
    query_geography,
)


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


def get_traffic_sources(days: int = 28) -> dict:
    """
    Get top search terms that find your videos.

    Args:
        days: Number of days to look back (default: 28)

    Returns:
        Dict with top search terms and view counts
    """
    # Check cache
    params = {"days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_traffic_sources", params_hash)
    if cached:
        return cached

    # Fetch fresh data
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_traffic_sources(start, end)
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [])
        top_terms = []
        for row in rows:
            top_terms.append({
                "term": row[0],
                "views": int(row[1])
            })

        result = {
            "top_search_terms": top_terms,
            "period_days": days,
        }

        # Cache result (6 hour TTL)
        cache_tool_result("get_traffic_sources", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_audience_demographics(days: int = 28) -> dict:
    """
    Get audience demographics by age and gender.

    Args:
        days: Number of days to look back (default: 28)

    Returns:
        Dict with age groups and gender breakdown
    """
    # Check cache
    params = {"days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_audience_demographics", params_hash)
    if cached:
        return cached

    # Fetch fresh data
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_demographics(start, end)
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [])
        
        age_groups = {}
        gender = {}
        
        for row in rows:
            age_group = row[0]
            gender_type = row[1]
            viewer_pct = float(row[2])
            
            if age_group not in age_groups:
                age_groups[age_group] = 0.0
            age_groups[age_group] += viewer_pct
            
            if gender_type not in gender:
                gender[gender_type] = 0.0
            gender[gender_type] += viewer_pct

        result = {
            "age_groups": age_groups,
            "gender": gender,
            "period_days": days,
        }

        # Cache result (6 hour TTL)
        cache_tool_result("get_audience_demographics", params_hash, result, ttl_hours=6)
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
    # Check cache
    params = {"video_id": video_id, "days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_retention_curve", params_hash)
    if cached:
        return cached

    # Fetch fresh data
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
            
            # Find first drop-off point (where watch_ratio drops below 0.5)
            if drop_off_point is None and watch_ratio < 0.5:
                drop_off_point = ratio

        result = {
            "video_id": video_id,
            "curve": curve,
            "drop_off_point": drop_off_point,
            "period_days": days,
        }

        # Cache result (6 hour TTL)
        cache_tool_result("get_retention_curve", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_device_breakdown(days: int = 28) -> dict:
    """
    Get device type breakdown.

    Args:
        days: Number of days to look back (default: 28)

    Returns:
        Dict with device breakdown by views and percentage
    """
    # Check cache
    params = {"days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_device_breakdown", params_hash)
    if cached:
        return cached

    # Fetch fresh data
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_device_types(start, end)
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [])
        
        devices = {}
        total_views = 0
        
        for row in rows:
            device_type = row[0]
            views = int(row[1])
            watch_time = float(row[2])
            
            devices[device_type] = {
                "views": views,
                "watch_time_minutes": watch_time,
            }
            total_views += views
        
        # Calculate percentages
        for device_type in devices:
            devices[device_type]["pct"] = devices[device_type]["views"] / total_views * 100 if total_views > 0 else 0.0

        result = {
            "devices": devices,
            "period_days": days,
        }

        # Cache result (6 hour TTL)
        cache_tool_result("get_device_breakdown", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_daily_views(days: int = 28) -> dict:
    """
    Get daily views time series.

    Args:
        days: Number of days to look back (default: 28)

    Returns:
        Dict with daily views, watch time, and subscriber gains
    """
    # Check cache
    params = {"days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_daily_views", params_hash)
    if cached:
        return cached

    # Fetch fresh data
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_daily_views(start, end)
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [])
        
        days_data = []
        for row in rows:
            days_data.append({
                "date": row[0],
                "views": int(row[1]),
                "watch_time_minutes": float(row[2]),
                "subs": int(row[3]) if len(row) > 3 else 0,
            })

        result = {
            "days": days_data,
            "period_days": days,
        }

        # Cache result (6 hour TTL)
        cache_tool_result("get_daily_views", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_geographic_breakdown(days: int = 28) -> dict:
    """
    Get geographic breakdown by country.

    Args:
        days: Number of days to look back (default: 28)

    Returns:
        Dict with top countries by views
    """
    # Check cache
    params = {"days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_geographic_breakdown", params_hash)
    if cached:
        return cached

    # Fetch fresh data
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_geography(start, end)
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [])
        
        countries = []
        total_views = sum(int(row[1]) for row in rows)
        
        for row in rows:
            country = row[0]
            views = int(row[1])
            watch_time = float(row[2])
            
            countries.append({
                "country": country,
                "views": views,
                "watch_time_minutes": watch_time,
                "pct": views / total_views * 100 if total_views > 0 else 0.0,
            })

        result = {
            "countries": countries,
            "period_days": days,
        }

        # Cache result (6 hour TTL)
        cache_tool_result("get_geographic_breakdown", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}
