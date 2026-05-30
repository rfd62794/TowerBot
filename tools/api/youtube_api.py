"""YouTube API client — raw API calls only."""

import os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from tools.api._handler import BaseAPIHandler


class YouTubeAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "youtube"

    def _get_credentials(self) -> Credentials:
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

    def _build_analytics_client(self):
        """Build YouTube Analytics API client."""
        creds = self._get_credentials()
        return build("youtubeAnalytics", "v2", credentials=creds)

    def _build_data_client(self):
        """Build YouTube Data API client."""
        creds = self._get_credentials()
        return build("youtube", "v3", credentials=creds)


    def query_channel_report(self, start_date: str, end_date: str, metrics: str) -> dict:
        """
        Query YouTube Analytics API for channel report.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            metrics: Comma-separated metrics (e.g., "views,estimatedMinutesWatched,subscribersGained")

        Returns:
            Raw API response or error dict
        """
        params_hash = self.hash(start_date, end_date, metrics)

        def _live():
            client = self._build_analytics_client()
            response = client.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics=metrics,
            ).execute()
            return {"raw": response}

        return self.call("channel_report", params_hash, _live)


    def query_video_report(self, video_id: str, start_date: str, end_date: str, metrics: str, dimensions: str = None) -> dict:
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
        params_hash = self.hash(video_id, start_date, end_date)

        def _live():
            client = self._build_analytics_client()
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

        return self.call("video_report", params_hash, _live)


    # UNUSED — not migrated
    def search_youtube(self, query: str, days: int, max_results: int = 10) -> dict:
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
            client = self._build_data_client()
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

    def get_video_statistics(self, video_ids: list[str]) -> dict:
        """
        Get statistics and metadata for YouTube videos.

        Args:
            video_ids: List of YouTube video IDs

        Returns:
            Raw API response or error dict
        """
        params_hash = self.hash(tuple(sorted(video_ids)))

        def _live():
            client = self._build_data_client()
            response = client.videos().list(
                part="statistics,snippet",
                id=",".join(video_ids)
            ).execute()
            return {"raw": response}

        return self.call("video_statistics", params_hash, _live)


    def get_channel_uploads_playlist_id(self) -> dict:
        """
        Get the uploads playlist ID for the authenticated channel.

        Returns:
            Raw API response or error dict
        """
        def _live():
            client = self._build_data_client()
            response = client.channels().list(
                part="contentDetails",
                mine=True
            ).execute()
            return {"raw": response}

        return self.call("playlist_id", self.hash(), _live)

    def get_playlist_items(self, playlist_id: str, max_results: int = 10) -> dict:
        """
        Get items from a playlist.

        Args:
            playlist_id: YouTube playlist ID
            max_results: Maximum results to return

        Returns:
            Raw API response or error dict
        """
        params_hash = self.hash(playlist_id, max_results)

        def _live():
            client = self._build_data_client()
            response = client.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=max_results
            ).execute()
            return {"raw": response}

        return self.call("playlist_items", params_hash, _live)


    def query_traffic_sources(self, start_date: str, end_date: str) -> dict:
        """
        Query YouTube Analytics for traffic sources (search terms).

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Raw API response or error dict
        """
        params_hash = self.hash(start_date, end_date)

        def _live():
            client = self._build_analytics_client()
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

        return self.call("traffic_sources", params_hash, _live)

    def query_demographics(self, start_date: str, end_date: str) -> dict:
        """
        Query YouTube Analytics for audience demographics.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Raw API response or error dict
        """
        params_hash = self.hash(start_date, end_date)

        def _live():
            client = self._build_analytics_client()
            response = client.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                dimensions="ageGroup,gender",
                metrics="viewerPercentage"
            ).execute()
            return {"raw": response}

        return self.call("demographics", params_hash, _live)

    def query_retention_curve(self, video_id: str, start_date: str, end_date: str) -> dict:
        """
        Query YouTube Analytics for retention curve.

        Args:
            video_id: YouTube video ID
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Raw API response or error dict
        """
        params_hash = self.hash(video_id, start_date, end_date)

        def _live():
            client = self._build_analytics_client()
            response = client.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                dimensions="elapsedVideoTimeRatio",
                metrics="audienceWatchRatio,relativeRetentionPerformance",
                filters=f"video=={video_id}"
            ).execute()
            return {"raw": response}

        return self.call("retention_curve", params_hash, _live)


    def query_device_types(self, start_date: str, end_date: str) -> dict:
        """
        Query YouTube Analytics for device breakdown.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Raw API response or error dict
        """
        params_hash = self.hash(start_date, end_date)

        def _live():
            client = self._build_analytics_client()
            response = client.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                dimensions="deviceType",
                metrics="views,estimatedMinutesWatched"
            ).execute()
            return {"raw": response}

        return self.call("device_types", params_hash, _live)

    def query_daily_views(self, start_date: str, end_date: str) -> dict:
        """
        Query YouTube Analytics for daily views time series.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Raw API response or error dict
        """
        params_hash = self.hash(start_date, end_date)

        def _live():
            client = self._build_analytics_client()
            response = client.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                dimensions="day",
                metrics="views,estimatedMinutesWatched,subscribersGained"
            ).execute()
            return {"raw": response}

        return self.call("daily_views", params_hash, _live)

    def query_geography(self, start_date: str, end_date: str) -> dict:
        """
        Query YouTube Analytics for geographic breakdown.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Raw API response or error dict
        """
        params_hash = self.hash(start_date, end_date)

        def _live():
            client = self._build_analytics_client()
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

        return self.call("geography", params_hash, _live)


# Module-level instance
youtube_api = YouTubeAPIHandler()


# Backwards compat module-level functions
def query_channel_report(start_date: str, end_date: str, metrics: str) -> dict:
    return youtube_api.query_channel_report(start_date, end_date, metrics)


def query_video_report(video_id: str, start_date: str, end_date: str, metrics: str, dimensions: str = None) -> dict:
    return youtube_api.query_video_report(video_id, start_date, end_date, metrics, dimensions)


def get_video_statistics(video_ids: list[str]) -> dict:
    return youtube_api.get_video_statistics(video_ids)


def get_channel_uploads_playlist_id() -> dict:
    return youtube_api.get_channel_uploads_playlist_id()


def get_playlist_items(playlist_id: str, max_results: int = 10) -> dict:
    return youtube_api.get_playlist_items(playlist_id, max_results)


def query_traffic_sources(start_date: str, end_date: str) -> dict:
    return youtube_api.query_traffic_sources(start_date, end_date)


def query_demographics(start_date: str, end_date: str) -> dict:
    return youtube_api.query_demographics(start_date, end_date)


def query_retention_curve(video_id: str, start_date: str, end_date: str) -> dict:
    return youtube_api.query_retention_curve(video_id, start_date, end_date)


def query_device_types(start_date: str, end_date: str) -> dict:
    return youtube_api.query_device_types(start_date, end_date)


def query_daily_views(start_date: str, end_date: str) -> dict:
    return youtube_api.query_daily_views(start_date, end_date)


def query_geography(start_date: str, end_date: str) -> dict:
    return youtube_api.query_geography(start_date, end_date)


# Backwards compat for internal functions used by other modules
def _get_credentials() -> Credentials:
    return youtube_api._get_credentials()


def search_youtube(query: str, days: int, max_results: int = 10) -> dict:
    return youtube_api.search_youtube(query, days, max_results)

