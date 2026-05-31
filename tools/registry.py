"""
Canonical source for ALL tool definitions.
This is the only file the agent imports tool metadata from.

No circular imports possible because:
  registry.py imports tool functions
  (tools/gmail.py, tools/goals.py, etc.)
  Tool function files do NOT import from registry.py
  — they just define functions and classes.
  
  The import graph is a tree, not a cycle.
"""

# ─── Imports — tool functions only ────────
from .content.channel import (
    get_channel_summary,
    get_daily_views,
    get_audience_demographics,
    get_device_breakdown,
    get_geographic_breakdown,
)
from .content.videos import (
    get_top_videos,
    get_video_analytics,
    get_retention_curve,
)
from .content.discovery import (
    get_traffic_sources,
)
from .games.recommendations import get_content_recommendations
from .games.metrics import get_game_metrics, get_installed_games, get_sale_info
from .search.search_tools import web_search, news_search, wiki_lookup, reddit_search, get_weather, fetch_url, get_weather_forecast
from .productivity.goals import (
    save_commitment,
    get_goals_list,
    get_goal_detail,
    get_current_plan,
    get_tasks_today,
    get_upcoming_tasks,
    update_task,
    add_new_task,
    suggest_goal_progress,
)
from .productivity.calendar import get_today_schedule, get_upcoming_events, check_availability
from .communication.gmail import (
    get_inbox_summary,
    get_all_inbox_summary,
    search_email,
    check_sender,
    check_sender_all,
    read_email,
)
from .productivity.personal import (
    add_personal_task,
    list_personal_tasks,
    complete_personal_task,
    snooze_personal_task,
    delete_personal_task,
)
from .meta.meta import think, get_current_datetime, calculate

# Memory tools — defined in bot/memory.py, imported here
from bot.memory import (
    tool_save_memory,
    tool_update_memory,
    tool_retire_memory,
    tool_get_memories,
)

# ─── Tool definitions ─────────────────────
# One entry per tool.
# Shape: {
#   "fn": callable,
#   "definition": {OpenAI function schema}
# }

TOOL_REGISTRY = {
    "get_youtube_stats": {
        "fn": get_channel_summary,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_youtube_stats",
                "description": "WHEN: User asks about channel performance, views, watch time, subscribers, how the channel is doing, weekly stats, numbers, analytics overview, 'how did we do'. Also call at start of any content strategy conversation.\n\nRETURNS: views (int), watch_time_minutes (float), subscribers_gained (int), start_date, end_date, period_days. If history exists: trend dict with views_prev, views_change_pct, subs_prev, subs_change_pct.\n\nDO NOT CALL: if already called this conversation and user hasn't asked for a refresh. Do not call for per-video questions — use get_video_analytics instead. Do not call for traffic/demographics — use dedicated tools.\n\nCHAIN: Follow with get_top_videos if user wants to know which videos drove performance.",
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
                "description": "WHEN: User asks which videos performed best, top Shorts, what got the most views, recent uploads, what's gaining traction, 'what went up recently', 'which video'.\n\nRETURNS: List of videos each with video_id, title (human readable, not just ID), views (int), published_at (date string). Ordered by views descending.\n\nDO NOT CALL: for channel totals — use get_youtube_stats instead. Do not call if you need retention or detailed per-video stats — use get_video_analytics with the video_id.\n\nCHAIN: Use returned video_id values to call get_video_analytics or get_retention_curve for deeper per-video analysis.",
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
                "description": "WHEN: User asks what to record tonight, what game to play for content, 'what should I stream', content ideas, 'what's underserved on YouTube'. Also call when user asks for a content strategy recommendation.\n\nRETURNS: count (int), recommendations list — each with name, appid, playtime_hours, composite_score (higher = better opportunity), content_demand_score, recent_upload_count. Scores combine your playtime with YouTube demand signal.\n\nDO NOT CALL: for specific game data — use get_game_metrics instead. This is a ranked list, not per-game details.\n\nCHAIN: Follow with get_game_metrics on the top result if user wants deeper data on a specific recommendation.",
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
                "description": "WHEN: User asks how a specific game is doing, player counts, 'is Raccoin growing', 'how is Duckov performing', whether a game is worth recording, YouTube coverage gap for a specific game.\n\nRETURNS: name, appid, your_playtime_hours, steam_owners (range string), players_2weeks (int — recent active players), youtube_recent_uploads (int), youtube_top_views (int), content_gap ('none'/'low'/'medium'/'high'), verdict (one sentence opportunity assessment). If history exists: players_change_pct trend. Returns error dict if game not found.\n\nDO NOT CALL: with an AppID — takes name only. Do not call for ranked recommendations — use get_content_recommendations instead.\n\nCHAIN: Call get_sale_info after if user also wants pricing information.",
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
                "description": "WHEN: User asks what games are installed right now, 'what can I record tonight without downloading', 'what's ready to play', available games on this machine.\n\nRETURNS: count (int), games list — each with name, appid, playtime_hours. Sorted by playtime descending. Filters to games with at least 1 hour played.\n\nDO NOT CALL: for content recommendations — use get_content_recommendations instead. This is inventory only, not strategy.",
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
                "description": "WHEN: User asks how a specific video performed, retention on a specific Short, stats on 'the EIC one', 'last night's upload', or any question about one specific video. Also call after get_top_videos if user wants details on a specific result.\n\nRETURNS: video_id, views (int), watch_time_minutes (float), avg_view_duration_seconds (float), avg_view_percentage (float — this is retention), period_days. Returns error dict if video has no data yet (too new) or ID is invalid.\n\nDO NOT CALL: without a valid video_id. Get video_id from get_top_videos first if you only have a title or description. Do not call for full channel stats.\n\nCHAIN: Call get_retention_curve after this if user wants to know exactly where viewers drop off in the video.",
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
                "description": "WHEN: User asks if a game is on sale, current price, 'should I buy X now', best price, historical low, 'is X discounted'.\n\nRETURNS: For each game: current_price (float), current_discount_pct (int), historical_low (float), on_sale (bool), store_name, store_url. Returns error entry per game if not found.\n\nDO NOT CALL: for game performance metrics — use get_game_metrics instead. Takes a list of game name strings. Always pass full game name not abbreviation.",
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
    "get_traffic_sources": {
        "fn": get_traffic_sources,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_traffic_sources",
                "description": "WHEN: User asks how viewers find the channel, what search terms work, which titles attract clicks, SEO questions, 'what are people searching for', 'how do they find me'.\n\nRETURNS: List of top search terms each with term (string) and views (int). Shows only YouTube search traffic — not suggested or browse traffic.\n\nDO NOT CALL: for overall channel stats. Do not call for per-video traffic — this is channel-wide search terms only.\n\nCHAIN: Use returned terms to inform title recommendations. Pair with get_top_videos to connect terms to performing content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Days to look back (default: 28)",
                            "default": 28,
                        }
                    },
                    "required": [],
                },
            },
        },
    },
    "get_audience_demographics": {
        "fn": get_audience_demographics,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_audience_demographics",
                "description": "WHEN: User asks who is watching, audience age, gender breakdown, 'who are my viewers', audience profile questions.\n\nRETURNS: age_groups dict (13-17, 18-24, 25-34, 35-44, 45-54, 55-64, 65+) each with viewer_percentage. gender dict with male/female/userSpecified percentages. period_days.\n\nDO NOT CALL: for performance metrics — use get_youtube_stats instead. This is purely audience composition data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Days to look back (default: 28)",
                            "default": 28,
                        }
                    },
                    "required": [],
                },
            },
        },
    },
    "get_retention_curve": {
        "fn": get_retention_curve,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_retention_curve",
                "description": "WHEN: User asks where viewers drop off, why a video lost viewers, hook analysis, 'at what point do they leave', 'is my intro working', retention questions about a specific video.\n\nRETURNS: video_id, curve (list of points each with ratio float 0-1 and watch_ratio float 0-1), drop_off_point (float — ratio where watch_ratio first drops below 0.5). Low watch_ratio early = hook problem.\n\nDO NOT CALL: without a valid video_id. Requires a specific video — not channel-wide. For average retention use get_video_analytics avg_view_percentage instead.\n\nCHAIN: Always call get_video_analytics first to confirm the video has data before pulling the full curve.",
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
    "get_device_breakdown": {
        "fn": get_device_breakdown,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_device_breakdown",
                "description": "WHEN: User asks what devices viewers use, mobile vs desktop split, 'should I optimize for mobile', 'what screen size are they on', device questions.\n\nRETURNS: devices dict with MOBILE, COMPUTER, TV, TABLET — each with views (int) and pct (float). period_days.\n\nDO NOT CALL: unless specifically asked about devices. Not needed for most conversations. Low-frequency tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Days to look back (default: 28)",
                            "default": 28,
                        }
                    },
                    "required": [],
                },
            },
        },
    },
    "get_daily_views": {
        "fn": get_daily_views,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_daily_views",
                "description": "WHEN: User asks about view trends over time, 'did views spike', 'which day performed best', 'show me the trend', daily breakdown, time series questions.\n\nRETURNS: days list — each entry has date (string), views (int), watch_time (float), subs (int). Ordered chronologically oldest to newest.\n\nDO NOT CALL: for totals — use get_youtube_stats. This is the time series breakdown only. Useful for spotting upload day spikes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Days to look back (default: 28)",
                            "default": 28,
                        }
                    },
                    "required": [],
                },
            },
        },
    },
    "get_geographic_breakdown": {
        "fn": get_geographic_breakdown,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_geographic_breakdown",
                "description": "WHEN: User asks where viewers are from, country breakdown, 'are my viewers international', 'which countries watch', geographic questions.\n\nRETURNS: countries list — each with country (2-letter code), views (int), pct (float). Ordered by views descending, top 25.\n\nDO NOT CALL: unless specifically asked about geography. Low-frequency tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Days to look back (default: 28)",
                            "default": 28,
                        }
                    },
                    "required": [],
                },
            },
        },
    },
    "web_search": {
        "fn": web_search,
        "definition": {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "WHEN: User asks about anything factual you are not certain about — current events, recent news, game releases, people, companies, prices, dates, facts. REQUIRED before answering any factual question where you might guess wrong. The EIC hallucination happened because this was not called. Do not repeat that.\n\nRETURNS: count (int), results list — each with title, url, body (snippet). May return empty list if no results found.\n\nDO NOT CALL: for Robert's own YouTube data — use get_youtube_stats tools instead. Do not call for Steam game data — use get_game_metrics instead. Do not call for Wikipedia topics — use wiki_lookup for cleaner results.\n\nCHAIN: Use wiki_lookup first for stable factual topics (games, people, places). Use web_search for current events and time-sensitive information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results to return (default: 5)",
                            "default": 5,
                        }
                    },
                    "required": ["query"],
                },
            },
        },
    },
    "news_search": {
        "fn": news_search,
        "definition": {
            "type": "function",
            "function": {
                "name": "news_search",
                "description": "WHEN: User asks about recent news, game updates, patch notes, announcements, 'what happened with X recently', trending topics, anything that changes day to day.\n\nRETURNS: count (int), results list — each with title, url, body, date, source. Ordered by recency.\n\nDO NOT CALL: for stable factual information — use wiki_lookup instead. Do not call for Robert's channel data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results to return (default: 5)",
                            "default": 5,
                        }
                    },
                    "required": ["query"],
                },
            },
        },
    },
    "wiki_lookup": {
        "fn": wiki_lookup,
        "definition": {
            "type": "function",
            "function": {
                "name": "wiki_lookup",
                "description": "WHEN: User asks about a game, person, place, company, concept, historical fact, or anything with a stable Wikipedia article. Call before answering factual questions about games you are not certain about — prevents hallucination.\n\nRETURNS: title, description (one line), extract (first paragraph), found (bool). If found=False: game or topic not on Wikipedia.\n\nDO NOT CALL: for current events or recent news — use news_search instead. Do not call for Robert's own content data.\n\nCHAIN: If wiki_lookup returns found=False, fall through to web_search for the same topic.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Topic to look up",
                        }
                    },
                    "required": ["topic"],
                },
            },
        },
    },
    "reddit_search": {
        "fn": reddit_search,
        "definition": {
            "type": "function",
            "function": {
                "name": "reddit_search",
                "description": "WHEN: User asks what people think about a game, community sentiment, 'is X worth playing', 'what does Reddit say about Y', player opinions, forum discussion about a game or topic.\n\nRETURNS: count (int), results list — each with title, score (upvotes), url, subreddit, num_comments. Ordered by relevance.\n\nDO NOT CALL: for factual game data — use get_game_metrics or wiki_lookup. Reddit is for sentiment, not facts.\n\nRECOMMENDED SUBREDDITS: incremental_games — idle/clicker games, patientgamers — general game opinions, indiegaming — indie game discussion, gamedev — developer community. Leave subreddit empty for broad search.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "subreddit": {
                            "type": "string",
                            "description": "Optional subreddit to search within",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return (default: 10)",
                            "default": 10,
                        }
                    },
                    "required": ["query"],
                },
            },
        },
    },
    "get_weather": {
        "fn": get_weather,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "WHEN: User asks about weather, temperature, 'should I open the window', 'is it raining', or when morning context is useful. Also called automatically by morning briefing.\n\nRETURNS: temp_f (float), condition (string — 'Clear skies', 'Rain', 'Thunderstorm' etc), wind_mph (float), precipitation_mm (float). Always South Florida location.\n\nDO NOT CALL: more than once per conversation unless user specifically asks for an update. Weather is cached for 1 hour.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
    },
    "get_weather_forecast": {
        "fn": get_weather_forecast,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_weather_forecast",
                "description": "WHEN: user asks about future weather, weekend plans, whether to expect rain.\n\nRETURNS: array of days with high_f, low_f, precipitation_pct, condition, day_of_week.\n\nDO NOT CALL: for current conditions (use get_weather).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Number of forecast days (1-7, default 3)",
                            "default": 3
                        }
                    },
                    "required": []
                }
            }
        }
    },
    "get_inbox_summary": {
        "fn": get_all_inbox_summary,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_inbox_summary",
                "description": "WHEN: Robert asks about email, 'any emails?', 'check my inbox', 'how many unread', 'what's in my email', 'did anyone email me'. Checks BOTH personal (cheater2478) and professional (RFDITServices) accounts if authorized.\n\nRETURNS: personal.unread_count, professional.unread_count, total_unread, recent messages from both. professional section present only if RFD token exists.\n\nDO NOT CALL: if user asks about a specific sender — use check_sender_all instead. DO NOT CALL: if user wants to search by topic — use search_email instead.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
    },
    "search_email": {
        "fn": search_email,
        "definition": {
            "type": "function",
            "function": {
                "name": "search_email",
                "description": "WHEN: Robert asks to find emails, 'find emails about X', 'search for Y in email', 'any emails mentioning Z', topic or keyword searches.\n\nRETURNS: query, count, messages list each with from, subject, date, snippet.\n\nPARAMS: query (Gmail search syntax — from:, subject:, is:unread, after:YYYY/MM/DD etc), max_results (int, default 5).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Gmail search query. Supports from:, subject:, is:unread, in:inbox, after:, before:, etc."},
                        "max_results": {"type": "integer", "description": "Max messages to return. Default 5."},
                    },
                    "required": ["query"],
                },
            },
        },
    },
    "check_sender_all": {
        "fn": check_sender_all,
        "definition": {
            "type": "function",
            "function": {
                "name": "check_sender_all",
                "description": "WHEN: Robert asks if a specific person replied or emailed, 'did X reply', 'any emails from Y', 'has Z responded'. Searches BOTH personal and professional inboxes and labels each result by account.\n\nRETURNS: sender, count, has_messages (bool), messages list — each message has account ('personal' or 'rfd'), from, subject, snippet.\n\nPARAMS: sender (email or name, required), unread_only (bool, default True).\n\nUSE THIS instead of check_sender when you want to search both accounts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sender": {"type": "string", "description": "Email address or name to check across both accounts"},
                        "unread_only": {"type": "boolean", "description": "Only return unread emails. Default true."},
                    },
                    "required": ["sender"],
                },
            },
        },
    },
    "check_sender": {
        "fn": check_sender,
        "definition": {
            "type": "function",
            "function": {
                "name": "check_sender",
                "description": "WHEN: Robert asks if a specific person replied or emailed, 'did X reply', 'any emails from Y', 'has Z responded', 'check if client emailed'.\n\nRETURNS: sender, count, has_messages (bool — False means no emails found), messages list with subject and snippet.\n\nPARAMS: sender (email address or name), unread_only (bool, default True).\n\nDO NOT CALL: for general inbox check — use get_inbox_summary instead.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sender": {"type": "string", "description": "Email address or name to check"},
                        "unread_only": {"type": "boolean", "description": "Only return unread emails. Default true."},
                    },
                    "required": ["sender"],
                },
            },
        },
    },
    "read_email": {
        "fn": read_email,
        "definition": {
            "type": "function",
            "function": {
                "name": "read_email",
                "description": "WHEN: Robert wants to read the content of a specific email, 'what does that email say', 'read that', 'what did they write'. Requires a message_id from a prior search.\n\nRETURNS: from, subject, date, body (first 2000 chars).\n\nPARAMS: message_id (string — get this from search_email or check_sender results first).\n\nDO NOT CALL: without a message_id. Always search first.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message_id": {"type": "string", "description": "Gmail message ID from a prior search result"},
                    },
                    "required": ["message_id"],
                },
            },
        },
    },
    "get_today_schedule": {
        "fn": get_today_schedule,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_today_schedule",
                "description": "WHEN: Robert asks what's on his calendar today, 'what do I have today', 'am I busy today', 'what's scheduled', any morning context about the day. Also called as part of daily briefing context.\n\nRETURNS: count (int), formatted (list of readable time — event strings), events list with title, start, end, location, all_day.\n\nDO NOT CALL: for future days — use get_upcoming_events instead.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
    },
    "get_upcoming_events": {
        "fn": get_upcoming_events,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_upcoming_events",
                "description": "WHEN: Robert asks about upcoming events, 'what's this week', 'anything coming up', 'what's on my calendar', 'am I free this weekend', schedule questions beyond today.\n\nRETURNS: count, days (int), formatted (list of readable strings), events list.\n\nPARAMS: days (int, default 7 — pass 14 for two weeks, 30 for a month).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "How many days ahead to look. Default 7."},
                    },
                    "required": [],
                },
            },
        },
    },
    "check_availability": {
        "fn": check_availability,
        "definition": {
            "type": "function",
            "function": {
                "name": "check_availability",
                "description": "WHEN: Robert asks if he is free on a specific date, 'am I busy Friday', 'is Saturday clear', 'do I have anything on June 15', 'is next Monday open'.\n\nRETURNS: date, busy (bool — True means has events), count, formatted list. busy=False means the day is clear.\n\nPARAMS: date (YYYY-MM-DD, required).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "Date to check in YYYY-MM-DD format"},
                    },
                    "required": ["date"],
                },
            },
        },
    },
    "add_personal_task": {
        "fn": add_personal_task,
        "definition": {
            "type": "function",
            "function": {
                "name": "add_personal_task",
                "description": "WHEN: Robert wants to add a reminder, to-do, or personal task. Triggers: 'remind me to X', 'add X to my list', 'I need to do X', 'don't let me forget X', 'every Monday do X', 'pick up X at Y time'.\n\nDIFFERENT FROM add_task: add_task = project task in weekly plan. add_personal_task = personal reminder or to-do with no goal linkage needed.\n\nRETURNS: status ('added'), id, title, due, recurrence if set.\n\nDO NOT CALL: for project tasks that belong in the weekly plan — use add_task instead.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "What to do"},
                        "due": {"type": "string", "description": "When — natural language ok: 'tomorrow', 'Friday at 6PM', 'YYYY-MM-DD'. Optional."},
                        "time": {"type": "string", "description": "Time of day as HH:MM. Optional — use if due doesn't include time."},
                        "recurrence": {"type": "string", "description": "Recurrence pattern — natural language ok: 'every Monday', 'every day', 'every weekday'. Optional."},
                        "notes": {"type": "string", "description": "Extra notes. Optional."},
                    },
                    "required": ["title"],
                },
            },
        },
    },
    "list_personal_tasks": {
        "fn": list_personal_tasks,
        "definition": {
            "type": "function",
            "function": {
                "name": "list_personal_tasks",
                "description": "WHEN: Robert asks what's on his list, personal reminders, 'what do I have today', to-do list, 'what am I forgetting', /todo command.\n\nRETURNS: filter, count, tasks list with id, title, due_date, due_time, recurrence, status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string", "enum": ["today", "upcoming", "overdue", "all"], "description": "Which tasks to show. Default: 'today'."},
                    },
                    "required": [],
                },
            },
        },
    },
    "complete_personal_task": {
        "fn": complete_personal_task,
        "definition": {
            "type": "function",
            "function": {
                "name": "complete_personal_task",
                "description": "WHEN: Robert says he did something, 'done with X', 'finished X', 'mark X done' for a personal task. If recurring, automatically creates next occurrence.\n\nRETURNS: status ('completed'), id, title, next_due if recurring.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer", "description": "ID of the personal task to mark done"},
                    },
                    "required": ["task_id"],
                },
            },
        },
    },
    "snooze_personal_task": {
        "fn": snooze_personal_task,
        "definition": {
            "type": "function",
            "function": {
                "name": "snooze_personal_task",
                "description": "WHEN: Robert says 'remind me later', 'snooze that', 'not now but later' for a personal task.\n\nRETURNS: status ('snoozed'), id, new_due datetime.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer", "description": "ID of the task to snooze"},
                        "minutes": {"type": "integer", "description": "Minutes to push forward. Default: 60."},
                    },
                    "required": ["task_id"],
                },
            },
        },
    },
    "delete_personal_task": {
        "fn": delete_personal_task,
        "definition": {
            "type": "function",
            "function": {
                "name": "delete_personal_task",
                "description": "WHEN: Robert says 'remove X', 'delete X', 'cancel X' for a personal task.\n\nRETURNS: status ('deleted'), id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer", "description": "ID of the task to delete"},
                    },
                    "required": ["task_id"],
                },
            },
        },
    },
    "save_commitment": {
        "fn": save_commitment,
        "definition": {
            "type": "function",
            "function": {
                "name": "save_commitment",
                "description": "WHEN: Robert says he WILL do something with a time reference or clear intention. Triggers: 'I'm going to X', 'I'll do X this weekend', 'I need to do X by Y', 'planning to X after Z', 'going to record X', 'will finish X by Y', 'I want to X before Y'.\n\nRETURNS: status ('saved'), description, deadline, commitment_id. Fires 📋 report to Telegram.\n\nDO NOT CALL: for tasks already in the weekly plan — use add_task instead. DO NOT CALL: for vague intentions with no time reference — acknowledge in response only.\n\nDIFFERENT FROM add_task: add_task = specific item in the weekly plan. save_commitment = promise Robert made that needs follow-up tracking.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "What Robert committed to do",
                        },
                        "deadline": {
                            "type": "string",
                            "description": "When — YYYY-MM-DD or natural language. Optional.",
                        },
                    },
                    "required": ["description"],
                },
            },
        },
    },
    "fetch_url": {
        "fn": fetch_url,
        "definition": {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "WHEN: A previous search returned a URL that needs deeper reading. User asks 'what does that article say', 'read that page', 'get more detail from that link'. A search snippet is clearly incomplete.\n\nRETURNS: title (str), content (str — first 3000 chars of page text), truncated (bool — more exists), char_count (int).\n\nDO NOT CALL: speculatively on every search result. Only when a specific URL's full content is needed. Never fetch without a URL from a prior search result. Never fetch login-required pages.\n\nCHAIN: Always call web_search or wiki_lookup first to find the URL. Then fetch_url for full content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The full URL to fetch including https:// prefix",
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "Maximum characters to return. Default 3000. Max 5000.",
                            "default": 3000,
                        },
                    },
                    "required": ["url"],
                },
            },
        },
    },
    "think": {
        "fn": think,
        "definition": {
            "type": "function",
            "function": {
                "name": "think",
                "description": "WHEN: Before a complex tool chain where multiple steps are needed. When the question requires planning before executing. When switching between topics or when resuming after a tool failure.\n\nWHY: Creates visible context that persists across model switches. If one model throttles and another takes over, the thought record lets the new model continue from where the previous model left off.\n\nRETURNS: thought recorded, ok=True. No side effects. No storage.\n\nDO NOT CALL: for every single message. Use for genuinely complex multi-step reasoning only.\n\nEXAMPLE: think('I need to find the top video first, then check its retention curve to see where viewers drop.') → then call get_top_videos() → then call get_retention_curve()",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Your reasoning step or plan",
                        },
                    },
                    "required": ["content"],
                },
            },
        },
    },
    "get_current_datetime": {
        "fn": get_current_datetime,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_current_datetime",
                "description": "WHEN: any time you need the current date, time, or day of week. Use before scheduling tasks, calculating deadlines, or any time-sensitive operation.\n\nRETURNS: datetime, date, time, day_of_week, timezone, unix timestamp.\n\nDO NOT CALL: for historical dates or date arithmetic (use calculate for that).",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    },
    "calculate": {
        "fn": calculate,
        "definition": {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "WHEN: math expressions, unit conversions, date arithmetic. Supported: +,-,*,/,**,%, sqrt, abs, round, floor, ceil, log, log10, sin, cos, tan, pi, e.\n\nRETURNS: result (number) and result_str (string).\n\nDO NOT CALL: for non-math expressions or string operations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Math expression to evaluate (e.g. '2 + 2', 'sqrt(144)', '(88 - 32) * 5/9')"
                        }
                    },
                    "required": ["expression"]
                }
            }
        }
    },
    # Memory tools
    "save_memory": {
        "fn": tool_save_memory,
        "definition": {
            "type": "function",
            "function": {
                "name": "save_memory",
                "description": "WHEN: Robert states a fact about himself, his projects, preferences, decisions, goals, people he mentions, or technical choices. Specific triggers: 'I'm working on X', 'I prefer Y', 'my Z is...', 'I decided to...', 'remember that...'. Save after learning anything that should persist across conversations.\n\nRETURNS: status ('saved'), key, layer, content.\n\nDO NOT CALL: for casual conversation, temporary context, things said in passing, or information already in memory. Check get_memories first if unsure whether something is already saved.\n\nNEVER save commitments as memories. When Robert says he WILL do something with a time reference — call save_commitment instead. That tool exists and handles tracking.\n\nLAYERS: technical — stack, tools, languages, patterns. project — active projects and their status. personal — life context, family, goals, style. business — work, clients, income, career. content — YouTube, games, series, schedule.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Short unique slug"},
                        "content": {"type": "string", "description": "The fact to remember"},
                        "layer": {
                            "type": "string",
                            "enum": ["technical", "project", "personal", "business", "content"],
                        },
                    },
                    "required": ["key", "content", "layer"],
                },
            },
        },
    },
    "update_memory": {
        "fn": tool_update_memory,
        "definition": {
            "type": "function",
            "function": {
                "name": "update_memory",
                "description": "WHEN: Robert corrects something you said, a fact has changed, a project status changed, a preference shifted. Triggers: 'actually it's...', 'that changed', 'I moved to...', 'we decided...', 'no longer...'. Update IMMEDIATELY when corrected. Do not wait or ask for confirmation.\n\nRETURNS: status ('updated'), key, reason, content.\n\nDO NOT CALL: to create new memory — use save_memory instead. Requires an existing key to update.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "content": {"type": "string", "description": "The new content"},
                        "reason": {"type": "string", "description": "What changed and why"},
                    },
                    "required": ["key", "content", "reason"],
                },
            },
        },
    },
    "retire_memory": {
        "fn": tool_retire_memory,
        "definition": {
            "type": "function",
            "function": {
                "name": "retire_memory",
                "description": "WHEN: A memory is no longer true and updating it would be misleading. Use when a project is abandoned, a fact is fully obsolete, or a preference no longer applies at all.\n\nRETURNS: status ('retired'), key, reason.\n\nDO NOT CALL: when information just changed — use update_memory instead. Retire only when the memory should stop being referenced entirely.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "reason": {"type": "string", "description": "Why it is retired"},
                    },
                    "required": ["key", "reason"],
                },
            },
        },
    },
    "get_memories": {
        "fn": tool_get_memories,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_memories",
                "description": "WHEN: Starting a new topic, answering a question about Robert's projects or preferences, before save_memory to check if key already exists. Call at the start of any conversation about a specific project or goal.\n\nRETURNS: status ('found'/'empty'), count (int), memories list — each with key, content, layer. Returns up to 5 closest matches.\n\nDO NOT CALL: for every single message. Call when context is needed, not reflexively. If you already retrieved memories this conversation on this topic — use them.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
        },
    },
    # Goals tools
    "get_goals": {
        "fn": get_goals_list,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_goals",
                "description": "WHEN: User asks about goals, long-term plans, 'what am I working toward', progress, 'Palm Beach', 'ReactReel', any goal by name. Also call when user asks 'what should I prioritize'.\n\nRETURNS: List of goals each with id, title, deadline, status, progress_pct, notes. Filter by status if needed.\n\nDO NOT CALL: for this week's tasks — use get_current_plan or get_tasks_today. Goals are long-term objectives only.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["active", "complete", "paused"],
                            "description": "Optional status filter"
                        },
                    },
                    "required": [],
                },
            },
        },
    },
    "get_goal": {
        "fn": get_goal_detail,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_goal",
                "description": "WHEN: User asks about a specific goal in detail, milestones for a goal, 'what's left for X', progress breakdown, or after get_goals when user wants to drill into one goal.\n\nRETURNS: Full goal object with milestones list (each with id, title, deadline, status) and associated tasks.\n\nDO NOT CALL: for the goals list — use get_goals instead. Requires a specific goal_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "goal_id": {"type": "string", "description": "Goal ID (e.g., palm_beach_2036)"},
                    },
                    "required": ["goal_id"],
                },
            },
        },
    },
    "get_current_plan": {
        "fn": get_current_plan,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_current_plan",
                "description": "WHEN: User asks what the plan is this week, 'what am I focused on', 'what's the weekly plan', or when giving context about current priorities.\n\nRETURNS: week_start, week_end, focus (string), notes, tasks list for this week.\n\nDO NOT CALL: for today's specific tasks — use get_tasks_today for that. This is the weekly overview.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
    },
    "get_tasks_today": {
        "fn": get_tasks_today,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_tasks_today",
                "description": "WHEN: User asks what to do today, today's tasks, 'what's on my list', morning planning, or any question about today's specific items.\n\nRETURNS: List of tasks each with id, title, due_date, status, scheduled_at. Filtered to today only.\n\nDO NOT CALL: for the weekly plan — use get_current_plan instead. Do not call for upcoming tasks beyond today — use get_upcoming_tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
    },
    "get_upcoming_tasks": {
        "fn": get_upcoming_tasks,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_upcoming_tasks",
                "description": "WHEN: User asks what's coming up, tasks in the next few days, upcoming scheduled items, 'what do I have this week', forward-looking task questions.\n\nRETURNS: List of tasks due within specified hours, each with id, title, due_date, scheduled_at, status.\n\nDO NOT CALL: for today's tasks — use get_tasks_today instead. Default 24 hours covers tomorrow.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "hours": {"type": "integer", "description": "Hours to look ahead (default: 24)"},
                    },
                    "required": [],
                },
            },
        },
    },
    "update_task": {
        "fn": update_task,
        "definition": {
            "type": "function",
            "function": {
                "name": "update_task",
                "description": "WHEN: User says they completed a task, 'I finished X', 'done with Y', 'mark X complete', task status changed. Requires task_id — get it from get_tasks_today or get_upcoming_tasks first.\n\nRETURNS: status ('updated'), task_id, new_status, title.\n\nDO NOT CALL: without a valid task_id. Never guess a task_id. Always retrieve tasks first to get the ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "complete", "cancelled"],
                        },
                    },
                    "required": ["task_id", "status"],
                },
            },
        },
    },
    "add_task": {
        "fn": add_new_task,
        "definition": {
            "type": "function",
            "function": {
                "name": "add_task",
                "description": "WHEN: User wants to add something to their plan, 'add a task', 'remind me to', 'I need to do X by Y', creating a new to-do item.\n\nRETURNS: status ('created'), task_id, title, due_date.\n\nDO NOT CALL: for commitments with vague deadlines — save to memory instead. Use only when there's a clear title and due date to work with.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Task title"},
                        "due_date": {"type": "string", "description": "Due date (YYYY-MM-DD)"},
                        "scheduled_at": {"type": "string", "description": "Optional scheduled datetime (YYYY-MM-DD HH:MM)"},
                        "milestone_id": {"type": "string", "description": "Optional milestone ID to link to"},
                    },
                    "required": ["title", "due_date"],
                },
            },
        },
    },
    "suggest_goal_progress": {
        "fn": suggest_goal_progress,
        "definition": {
            "type": "function",
            "function": {
                "name": "suggest_goal_progress",
                "description": "WHEN: User describes completing something that sounds like a milestone — 'I shipped the OAuth', 'I got my first customer', 'I deployed to Tower'. This does NOT update anything. It generates a suggestion string that gets sent to Telegram for confirmation. User must /confirm or /reject.\n\nRETURNS: suggestion text string for display. Does not modify any data.\n\nDO NOT CALL: to actually update goals — this is suggestion only. Never call without a milestone_id. Get milestone_id from get_goal first.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "milestone_id": {"type": "string", "description": "Milestone ID"},
                    },
                    "required": ["milestone_id"],
                },
            },
        },
    },
}

# ─── Convenience exports ──────────────────
ALL_TOOLS = [entry["definition"] for entry in TOOL_REGISTRY.values()]
TOOL_NAMES = list(TOOL_REGISTRY.keys())


def get_tool(name: str) -> dict | None:
    return TOOL_REGISTRY.get(name)


def get_tool_fn(name: str):
    entry = TOOL_REGISTRY.get(name)
    return entry["fn"] if entry else None
