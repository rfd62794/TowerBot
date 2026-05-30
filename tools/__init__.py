"""Tool plug-ins — extensible functions for AI agent."""

from .youtube import get_channel_summary, get_top_videos
from .recommendations import get_content_recommendations
from .games import get_game_metrics

TOOL_REGISTRY = {
    "get_youtube_stats": {
        "fn": get_channel_summary,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_youtube_stats",
                "description": "Get YouTube channel performance for last N days (views, watch time, subscribers).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Days to look back (default: 7)",
                            "default": 7,
                        }
                    },
                    "required": [],
                },
            },
        },
    },
    "get_top_videos": {
        "fn": get_top_videos,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_top_videos",
                "description": "Get top YouTube videos by views for last N days.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Days to look back (default: 7)",
                            "default": 7,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of videos to return (default: 10)",
                            "default": 10,
                        }
                    },
                    "required": [],
                },
            },
        },
    },
    "get_content_recommendations": {
        "fn": get_content_recommendations,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_content_recommendations",
                "description": "Get game recommendations for content recording based on playtime and YouTube demand. Call when asked what to record or stream tonight.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of recommendations to return (default: 5)",
                            "default": 5,
                        },
                        "min_playtime": {
                            "type": "number",
                            "description": "Minimum playtime hours threshold (default: 1.0)",
                            "default": 1.0,
                        }
                    },
                    "required": [],
                },
            },
        },
    },
    "get_game_metrics": {
        "fn": get_game_metrics,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_game_metrics",
                "description": "Get detailed metrics for a specific game by name. Call when asked how a game is performing, player counts, YouTube coverage, or whether it is worth recording. Takes game name not AppID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "game_name": {
                            "type": "string",
                            "description": "Name of the game (e.g. \"Raccoin\", \"Duckov\", \"EIC\")",
                        }
                    },
                    "required": ["game_name"],
                },
            },
        },
    },
}

