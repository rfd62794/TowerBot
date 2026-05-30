"""tools.youtube — YouTube tools package.

Re-exports all functions so external imports are unchanged:
    from tools.youtube import get_channel_summary, get_top_videos
"""

from tools.youtube.channel import (
    get_channel_summary,
    get_daily_views,
    get_geographic_breakdown,
    get_audience_demographics,
    get_device_breakdown,
)

from tools.youtube.videos import (
    get_top_videos,
    get_video_analytics,
    get_retention_curve,
)

from tools.youtube.discovery import (
    get_traffic_sources,
)

__all__ = [
    "get_channel_summary",
    "get_daily_views",
    "get_geographic_breakdown",
    "get_audience_demographics",
    "get_device_breakdown",
    "get_top_videos",
    "get_video_analytics",
    "get_retention_curve",
    "get_traffic_sources",
]
