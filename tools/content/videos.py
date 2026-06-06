"""Video-level YouTube tools."""

import hashlib
import json
import yaml
from datetime import datetime, timedelta
from tools._tool import BaseTool
from api.google.youtube_api import (
    query_video_report,
    query_retention_curve,
    get_channel_uploads_playlist_id,
    get_playlist_items,
    get_video_statistics,
    post_comment,
)


class VideoTools(BaseTool):
    """YouTube video-level tools with BaseTool pattern."""

    def get_top_videos(self, days: int = 7, limit: int = 10) -> dict:
        """
        Get top videos by views for last N days.

        Args:
            days: Number of days to look back (default: 7)
            limit: Maximum number of videos to return (default: 10)

        Returns:
            Dict with list of top videos and their stats.
        """
        try:
            playlist_response = get_channel_uploads_playlist_id()
            if "error" in playlist_response:
                return self.error(playlist_response["error"], code="api_failed")

            playlist_data = playlist_response["raw"]
            if not playlist_data.get("items"):
                return self.error("No channel data found", code="no_data")

            uploads_playlist_id = playlist_data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

            items_response = get_playlist_items(uploads_playlist_id, max_results=limit)
            if "error" in items_response:
                return self.error(items_response["error"], code="api_failed")

            items_data = items_response["raw"]
            video_ids = [item["contentDetails"]["videoId"] for item in items_data.get("items", [])]

            if not video_ids:
                return self.success({
                    "videos": [],
                    "period_days": days,
                })

            stats_response = get_video_statistics(video_ids)
            if "error" in stats_response:
                return self.error(stats_response["error"], code="api_failed")

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

            return self.success(result, stale_result=stats_response)
        except Exception as e:
            return self.error(str(e), code="exception")

    def get_video_analytics(self, video_id: str, days: int = 28) -> dict:
        """
        Get detailed performance metrics for a specific YouTube video.

        Args:
            video_id: YouTube video ID
            days: Number of days to look back (default: 28)

        Returns:
            Dict with detailed video metrics
        """
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            api_response = query_video_report(video_id, start, end, "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage", dimensions="video")
            if "error" in api_response:
                return self.error(api_response["error"], code="api_failed")

            response = api_response.get("raw")
            if response is None:
                return self.error("No analytics data", code="no_data")

            rows = response.get("rows", [])
            if not rows:
                return self.error("No data returned for this video", code="no_data")

            row = rows[0]
            result = {
                "video_id": video_id,
                "views": int(row[1]),
                "watch_time_minutes": float(row[2]),
                "avg_view_duration_seconds": float(row[3]),
                "avg_view_percentage": float(row[4]),
                "period_days": days,
            }

            return self.success(result, stale_result=api_response)
        except Exception as e:
            return self.error(str(e), code="exception")

    def get_retention_curve(self, video_id: str, days: int = 28) -> dict:
        """
        Get retention curve for a specific video.

        Args:
            video_id: YouTube video ID
            days: Number of days to look back (default: 28)

        Returns:
            Dict with retention curve data and drop-off point
        """
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            api_response = query_retention_curve(video_id, start, end)
            if "error" in api_response:
                return self.error(api_response["error"], code="api_failed")

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

            return self.success(result, stale_result=api_response)
        except Exception as e:
            return self.error(str(e), code="exception")

    def post_video_comment(self, video_id: str, text: str = None, series: str = None) -> dict:
        """
        Post a comment on a video using series template or provided text.
        Args:
            video_id: YouTube video ID
            text: Comment text (overrides template if provided)
            series: Series name to look up template (e.g. "Everything is Crab")
        Returns: {ok, comment_id, video_id, text_used}
        """
        try:
            # Load comment text from template if not provided
            if text is None:
                template_path = "config/comment_templates.yaml"
                try:
                    with open(template_path, "r") as f:
                        templates = yaml.safe_load(f)
                    
                    if series and series in templates.get("series", {}):
                        text = templates["series"][series]
                    else:
                        text = templates.get("default", "")
                except Exception as e:
                    return self.error(f"Failed to load comment templates: {e}", code="template_error")
            
            if not text:
                return self.error("No comment text provided and no template found", code="no_text")
            
            # Post comment via API
            api_response = post_comment(video_id, text)
            
            if not api_response.get("ok"):
                code = api_response.get("code", "api_error")
                return self.error(api_response.get("error", "Unknown error"), code=code)
            
            return self.success({
                "comment_id": api_response.get("comment_id"),
                "video_id": video_id,
                "text_used": text,
            }, stale_result=api_response)
        except Exception as e:
            return self.error(str(e), code="exception")


# Module-level instance
_video_tools = VideoTools()


# Backwards compat module-level functions
def get_top_videos(days: int = 7, limit: int = 10) -> dict:
    return _video_tools.get_top_videos(days, limit)


def get_video_analytics(video_id: str, days: int = 28) -> dict:
    return _video_tools.get_video_analytics(video_id, days)


def get_retention_curve(video_id: str, days: int = 28) -> dict:
    return _video_tools.get_retention_curve(video_id, days)


def post_video_comment(video_id: str, text: str = None, series: str = None) -> dict:
    return _video_tools.post_video_comment(video_id, text, series)
