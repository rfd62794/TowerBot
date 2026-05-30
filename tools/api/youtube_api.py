"""YouTube API client — raw API calls only."""

import os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


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
        from google.auth.transport.requests import Request
        creds.refresh(Request())

    return creds


def _build_analytics_client():
    """Build YouTube Analytics API client."""
    creds = _get_credentials()
    return build("youtubeAnalytics", "v2", credentials=creds)


def _build_data_client():
    """Build YouTube Data API client."""
    creds = _get_credentials()
    return build("youtube", "v3", credentials=creds)


def query_channel_report(start_date: str, end_date: str, metrics: str) -> dict:
    """
    Query YouTube Analytics API for channel report.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        metrics: Comma-separated metrics (e.g., "views,estimatedMinutesWatched,subscribersGained")

    Returns:
        Raw API response or error dict
    """
    try:
        client = _build_analytics_client()
        response = client.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics=metrics,
        ).execute()
        return {"raw": response}
    except Exception as e:
        return {"error": str(e)}


def query_video_report(video_id: str, start_date: str, end_date: str, metrics: str, dimensions: str = None) -> dict:
    """
    Query YouTube Analytics API for video report.

    Args:
        video_id: YouTube video ID
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        metrics: Comma-separated metrics
        dimensions: Optional dimensions (e.g., "video")

    Returns:
        Raw API response or error dict
    """
    try:
        client = _build_analytics_client()
        params = {
            "ids": "channel==MINE",
            "startDate": start_date,
            "endDate": end_date,
            "metrics": metrics,
        }
        if dimensions:
            params["dimensions"] = dimensions
        if video_id:
            params["filters"] = f"video=={video_id}"
        response = client.reports().query(**params).execute()
        return {"raw": response}
    except Exception as e:
        return {"error": str(e)}


def search_youtube(query: str, days: int, max_results: int = 10) -> dict:
    """
    Search YouTube Data API for videos.

    Args:
        query: Search query
        days: Search within last N days
        max_results: Maximum results to return

    Returns:
        Raw API response or error dict
    """
    try:
        client = _build_data_client()
        published_after = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        response = client.search().list(
            q=query,
            type="video",
            publishedAfter=published_after,
            maxResults=max_results,
            part="id,snippet"
        ).execute()
        return {"raw": response}
    except Exception as e:
        return {"error": str(e)}


def get_video_statistics(video_ids: list[str]) -> dict:
    """
    Get statistics and metadata for YouTube videos.

    Args:
        video_ids: List of YouTube video IDs

    Returns:
        Raw API response or error dict
    """
    try:
        client = _build_data_client()
        response = client.videos().list(
            part="statistics,snippet",
            id=",".join(video_ids)
        ).execute()
        return {"raw": response}
    except Exception as e:
        return {"error": str(e)}


def get_channel_uploads_playlist_id() -> dict:
    """
    Get the uploads playlist ID for the authenticated channel.

    Returns:
        Raw API response or error dict
    """
    try:
        client = _build_data_client()
        response = client.channels().list(
            part="contentDetails",
            mine=True
        ).execute()
        return {"raw": response}
    except Exception as e:
        return {"error": str(e)}


def get_playlist_items(playlist_id: str, max_results: int = 10) -> dict:
    """
    Get items from a playlist.

    Args:
        playlist_id: YouTube playlist ID
        max_results: Maximum results to return

    Returns:
        Raw API response or error dict
    """
    try:
        client = _build_data_client()
        response = client.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=max_results
        ).execute()
        return {"raw": response}
    except Exception as e:
        return {"error": str(e)}


def query_traffic_sources(start_date: str, end_date: str) -> dict:
    """
    Query YouTube Analytics for traffic sources (search terms).

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Raw API response or error dict
    """
    try:
        client = _build_analytics_client()
        response = client.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            dimensions="insightTrafficSourceDetail",
            filters="insightTrafficSourceType==YT_SEARCH",
            metrics="views",
            sort="-views",
            maxResults=25
        ).execute()
        return {"raw": response}
    except Exception as e:
        return {"error": str(e)}


def query_demographics(start_date: str, end_date: str) -> dict:
    """
    Query YouTube Analytics for audience demographics.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Raw API response or error dict
    """
    try:
        client = _build_analytics_client()
        response = client.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            dimensions="ageGroup,gender",
            metrics="viewerPercentage"
        ).execute()
        return {"raw": response}
    except Exception as e:
        return {"error": str(e)}


def query_retention_curve(video_id: str, start_date: str, end_date: str) -> dict:
    """
    Query YouTube Analytics for retention curve.

    Args:
        video_id: YouTube video ID
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Raw API response or error dict
    """
    try:
        client = _build_analytics_client()
        response = client.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            dimensions="elapsedVideoTimeRatio",
            metrics="audienceWatchRatio,relativeRetentionPerformance",
            filters=f"video=={video_id}"
        ).execute()
        return {"raw": response}
    except Exception as e:
        return {"error": str(e)}


def query_device_types(start_date: str, end_date: str) -> dict:
    """
    Query YouTube Analytics for device breakdown.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Raw API response or error dict
    """
    try:
        client = _build_analytics_client()
        response = client.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            dimensions="deviceType",
            metrics="views,estimatedMinutesWatched"
        ).execute()
        return {"raw": response}
    except Exception as e:
        return {"error": str(e)}


def query_daily_views(start_date: str, end_date: str) -> dict:
    """
    Query YouTube Analytics for daily views time series.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Raw API response or error dict
    """
    try:
        client = _build_analytics_client()
        response = client.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            dimensions="day",
            metrics="views,estimatedMinutesWatched,subscribersGained"
        ).execute()
        return {"raw": response}
    except Exception as e:
        return {"error": str(e)}


def query_geography(start_date: str, end_date: str) -> dict:
    """
    Query YouTube Analytics for geographic breakdown.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Raw API response or error dict
    """
    try:
        client = _build_analytics_client()
        response = client.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            dimensions="country",
            metrics="views,estimatedMinutesWatched",
            sort="-views",
            maxResults=25
        ).execute()
        return {"raw": response}
    except Exception as e:
        return {"error": str(e)}
