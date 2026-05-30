"""YouTube tool — fetch channel performance data via YouTube Analytics API."""

import os
import hashlib
import json
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from core.db import cache_tool_result, get_cached_tool_result


def _get_credentials() -> Credentials:
    """Load OAuth credentials from token file."""
    token_path = os.getenv("YOUTUBE_TOKEN_PATH", "config/youtube_token.json")
    client_secrets_path = os.getenv("YOUTUBE_CLIENT_SECRETS", "config/client_secret.json")

    if not os.path.exists(token_path):
        raise FileNotFoundError(
            f"OAuth token not found at {token_path}. "
            f"Run 'uv run python scripts/youtube_auth.py' to authorize."
        )

    # Load credentials from token file
    creds = Credentials.from_authorized_user_file(token_path)

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_path,
            scopes=[
                "https://www.googleapis.com/auth/yt-analytics.readonly",
                "https://www.googleapis.com/auth/youtube.readonly",
            ],
        )
        creds.refresh(flow)

    return creds


def _build_analytics_client():
    """Build YouTube Analytics API client."""
    creds = _get_credentials()
    return build("youtubeAnalytics", "v2", credentials=creds)


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
        client = _build_analytics_client()
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        response = client.reports().query(
            ids="channel==MINE",
            startDate=start,
            endDate=end,
            metrics="views,estimatedMinutesWatched,subscribersGained",
        ).execute()

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
        client = _build_analytics_client()

        response = client.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,subscribersGained",
        ).execute()

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
        client = _build_analytics_client()
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        response = client.reports().query(
            ids="channel==MINE",
            startDate=start,
            endDate=end,
            dimensions="video",
            metrics="views,estimatedMinutesWatched",
            sort="-views",
            max_results=limit,
        ).execute()

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
