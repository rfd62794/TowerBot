"""MCP server configuration.

Curated set of tools exposed via MCP. Manual configuration — faster to build,
clean upgrade path to marker classes when needed.
"""

# Tools safe to expose via MCP (both stdio and SSE)
# Excludes: internal tools (think, name_thread, audit_repo_compliance, system tools)
# Includes: memory, calendar, email, itch, YouTube, blog, reddit, games, search
MCP_EXPOSED_TOOLS = {
    # Memory tools
    "save_memory",
    "update_memory",
    "retire_memory",
    "get_memories",
    # Calendar
    "get_today_schedule",
    "get_upcoming_events",
    "check_availability",
    # Email
    "get_inbox_summary",
    "search_email",
    "check_sender_all",
    # Games
    "get_itch_stats",
    "get_game_metrics",
    "get_content_recommendations",
    "get_installed_games",
    "get_sale_info",
    # YouTube
    "get_youtube_stats",
    "get_top_videos",
    "get_video_analytics",
    "get_traffic_sources",
    "get_audience_demographics",
    "get_retention_curve",
    "get_device_breakdown",
    "get_daily_views",
    "get_geographic_breakdown",
    # Blog
    "get_blog_posts",
    "create_blog_draft",
    # Reddit
    "reddit_search",
    # Search
    "web_search",
    "news_search",
    "wiki_lookup",
    "get_weather",
    "get_weather_forecast",
    # Productivity
    "get_goals_list",
    "get_goal_detail",
    "get_current_plan",
    "get_tasks_today",
    "get_upcoming_tasks",
    # Personal tasks
    "add_personal_task",
    "list_personal_tasks",
    "complete_personal_task",
    # Repo tools (read-only)
    "read_local_file",
    "list_local_dir",
    "search_local_code",
    "inspect_repo",
}
