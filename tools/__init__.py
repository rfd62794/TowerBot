"""Tool plug-ins — extensible functions for AI agent."""

from .youtube import (
    get_channel_summary,
    get_top_videos,
    get_video_analytics,
    get_traffic_sources,
    get_audience_demographics,
    get_retention_curve,
    get_device_breakdown,
    get_daily_views,
    get_geographic_breakdown,
)
from .recommendations import get_content_recommendations
from .games import get_game_metrics, get_installed_games, get_sale_info
from .search_tools import web_search, news_search, wiki_lookup, reddit_search, get_weather, fetch_url
from .goals import save_commitment
from .calendar import get_today_schedule, get_upcoming_events, check_availability
from .gmail import (
    get_inbox_summary, get_all_inbox_summary,
    search_email, check_sender, check_sender_all, read_email,
)
from .personal import (
    add_personal_task,
    list_personal_tasks,
    complete_personal_task,
    snooze_personal_task,
    delete_personal_task,
)
from .meta import think

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
}

