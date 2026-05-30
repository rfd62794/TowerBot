"""Tool plug-ins — extensible functions for AI agent."""

from .youtube import get_channel_summary, get_top_videos, get_video_analytics
from .recommendations import get_content_recommendations
from .games import get_game_metrics, get_installed_games, get_sale_info

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
    "get_installed_games": {
        "fn": get_installed_games,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_installed_games",
                "description": "Get currently installed games from Steam library. Call when asked what can be recorded right now or what games are available.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
    },
    "get_video_analytics": {
        "fn": get_video_analytics,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_video_analytics",
                "description": "Get detailed performance metrics for a specific YouTube video by video ID. Call when asked how a specific video or Short performed. Use get_top_videos first if you need to find the video_id from a title.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "video_id": {
                            "type": "string",
                            "description": "YouTube video ID",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to look back (default: 28)",
                            "default": 28,
                        }
                    },
                    "required": ["video_id"],
                },
            },
        },
    },
    "get_sale_info": {
        "fn": get_sale_info,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_sale_info",
                "description": "Check current sale prices and historical lows for games via IsThereAnyDeal. Call when asked if a game is on sale, current price, or best price to buy.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "game_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of game names to check",
                        }
                    },
                    "required": ["game_names"],
                },
            },
        },
    },
}

