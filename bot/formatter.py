"""Telegram message formatter — converts responses to HTML parse mode."""

import re
from typing import Tuple

# Tool icon and name mappings for thinking thread display
TOOL_ICONS = {
    # YouTube/Content
    "get_youtube_stats": "📊",
    "get_top_videos": "📈",
    "get_video_analytics": "🎬",
    "get_traffic_sources": "🔍",
    "get_audience_demographics": "👥",
    "get_retention_curve": "📉",
    "get_device_breakdown": "📱",
    "get_daily_views": "📅",
    "get_geographic_breakdown": "🌍",
    # Games
    "get_content_recommendations": "🎮",
    "get_game_metrics": "🎯",
    "get_installed_games": "💾",
    "get_sale_info": "💰",
    "get_itch_stats": "🛒",
    # Search/Web
    "web_search": "🔍",
    "news_search": "📰",
    "wiki_lookup": "📖",
    "reddit_search": "💬",
    "get_weather": "🌤️",
    "get_weather_forecast": "📆",
    "get_pypi_stats": "📦",
    "get_recent_commits": "📝",
    "fetch_url": "🌐",
    # Email
    "get_inbox_summary": "📧",
    "search_email": "🔎",
    "check_sender_all": "👤",
    "check_sender": "👤",
    "read_email": "📨",
    # Blog
    "get_blog_posts": "📝",
    "get_blog_post": "📄",
    "create_blog_draft": "✍️",
    "update_blog_post": "✏️",
    "set_post_excerpt": "📋",
    "get_blog_categories": "📁",
    "set_post_categories": "🏷️",
    "set_post_tags": "🏷️",
    "schedule_blog_post": "📅",
    "search_blog_posts": "🔍",
    "advance_post_pipeline": "➡️",
    # Goals/Productivity
    "save_commitment": "📋",
    "get_goals_list": "🎯",
    "get_goal_detail": "📌",
    "get_current_plan": "📅",
    "get_tasks_today": "✅",
    "get_upcoming_tasks": "📆",
    "update_task": "✏️",
    "add_new_task": "➕",
    "suggest_goal_progress": "💡",
    "get_today_schedule": "🕐",
    "get_upcoming_events": "📅",
    "check_availability": "🕒",
    # Personal Tasks
    "add_personal_task": "➕",
    "list_personal_tasks": "📋",
    "complete_personal_task": "✅",
    "snooze_personal_task": "⏰",
    "delete_personal_task": "🗑️",
    # Meta
    "think": "💭",
    "get_current_datetime": "🕐",
    "calculate": "🔢",
    "run_openagent": "🤖",
    # Repo
    "read_local_file": "📄",
    "list_local_dir": "📁",
    "search_local_code": "🔍",
    "audit_repo_compliance": "🔬",
    "analyze_code_quality": "📊",
    "analyze_dependencies": "🔗",
    "find_opportunities": "💡",
    "analyze_documentation_alignment": "📖",
    "inspect_repo": "🔎",
    "generate_strategic_analysis": "📈",
    "read_current_state": "📋",
    "elaborate_task": "✍️",
    "generate_directive": "📜",
    # Memory
    "save_memory": "🧠",
    "update_memory": "✏️",
    "retire_memory": "🗑️",
    "get_memories": "🔍",
}

TOOL_NAMES = {
    # YouTube/Content
    "get_youtube_stats": "Pulling YouTube stats",
    "get_top_videos": "Getting top videos",
    "get_video_analytics": "Analyzing video performance",
    "get_traffic_sources": "Checking traffic sources",
    "get_audience_demographics": "Getting audience data",
    "get_retention_curve": "Analyzing retention",
    "get_device_breakdown": "Checking device types",
    "get_daily_views": "Getting daily view trends",
    "get_geographic_breakdown": "Getting geographic data",
    # Games
    "get_content_recommendations": "Finding content ideas",
    "get_game_metrics": "Checking game performance",
    "get_installed_games": "Listing installed games",
    "get_sale_info": "Checking sale prices",
    "get_itch_stats": "Getting itch.io stats",
    # Search/Web
    "web_search": "Searching the web",
    "news_search": "Searching news",
    "wiki_lookup": "Looking up Wikipedia",
    "reddit_search": "Searching Reddit",
    "get_weather": "Getting weather",
    "get_weather_forecast": "Getting forecast",
    "get_pypi_stats": "Getting package stats",
    "get_recent_commits": "Getting recent commits",
    "fetch_url": "Fetching URL content",
    # Email
    "get_inbox_summary": "Checking inbox",
    "search_email": "Searching emails",
    "check_sender_all": "Checking sender across accounts",
    "check_sender": "Checking sender",
    "read_email": "Reading email",
    # Blog
    "get_blog_posts": "Getting blog posts",
    "get_blog_post": "Getting blog post",
    "create_blog_draft": "Creating draft",
    "update_blog_post": "Updating post",
    "set_post_excerpt": "Setting excerpt",
    "get_blog_categories": "Getting categories",
    "set_post_categories": "Setting categories",
    "set_post_tags": "Setting tags",
    "schedule_blog_post": "Scheduling post",
    "search_blog_posts": "Searching posts",
    "advance_post_pipeline": "Advancing pipeline",
    # Goals/Productivity
    "save_commitment": "Saving commitment",
    "get_goals_list": "Getting goals",
    "get_goal_detail": "Getting goal details",
    "get_current_plan": "Getting current plan",
    "get_tasks_today": "Getting today's tasks",
    "get_upcoming_tasks": "Getting upcoming tasks",
    "update_task": "Updating task",
    "add_new_task": "Adding task",
    "suggest_goal_progress": "Suggesting progress",
    "get_today_schedule": "Getting schedule",
    "get_upcoming_events": "Getting events",
    "check_availability": "Checking availability",
    # Personal Tasks
    "add_personal_task": "Adding personal task",
    "list_personal_tasks": "Listing personal tasks",
    "complete_personal_task": "Completing task",
    "snooze_personal_task": "Snoozing task",
    "delete_personal_task": "Deleting task",
    # Meta
    "think": "Thinking",
    "get_current_datetime": "Getting time",
    "calculate": "Calculating",
    "run_openagent": "Running OpenAgent",
    # Repo
    "read_local_file": "Reading file",
    "list_local_dir": "Listing directory",
    "search_local_code": "Searching code",
    "audit_repo_compliance": "Auditing repo",
    "analyze_code_quality": "Analyzing code quality",
    "analyze_dependencies": "Analyzing dependencies",
    "find_opportunities": "Finding opportunities",
    "analyze_documentation_alignment": "Checking documentation",
    "inspect_repo": "Inspecting repo",
    "generate_strategic_analysis": "Generating analysis",
    "read_current_state": "Reading state",
    "elaborate_task": "Elaborating task",
    "generate_directive": "Generating directive",
    # Memory
    "save_memory": "Saving memory",
    "update_memory": "Updating memory",
    "retire_memory": "Retiring memory",
    "get_memories": "Retrieving memories",
}


def get_tool_display(tool_name: str) -> Tuple[str, str]:
    """Return (icon, name) for tool, with generic fallback."""
    icon = TOOL_ICONS.get(tool_name, "⚙️")
    name = TOOL_NAMES.get(tool_name, "Working")
    return icon, name


def format_response(text: str) -> str:
    """
    Convert response text to Telegram HTML parse mode.
    
    Rules:
    - Strip markdown table syntax (pipes, headers)
    - Convert **bold** to <b>bold</b>
    - Convert *italic* to <i>italic</i>
    - Convert `code` to <code>code</code>
    - Escape special chars (<, >, &) outside tags
    - Flatten nested bullet indentation
    - Chunk at natural paragraph breaks (double newlines)
    """
    if not text:
        return text
    
    # Remove markdown table pipes
    text = re.sub(r'\|', '', text)
    
    # Convert markdown headers to bold HTML
    text = re.sub(r'^###\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^##\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^#\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    
    # Convert markdown bold to HTML bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    
    # Convert markdown italic to HTML italic
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    
    # Convert markdown code to HTML code
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    
    # Escape special characters outside of HTML tags
    # This is a simple approach - escape <, >, & when not part of a tag
    def escape_special_chars(match):
        full_match = match.group(0)
        # If it's an HTML tag, don't escape
        if full_match.startswith('<') and full_match.endswith('>'):
            return full_match
        # Otherwise escape
        return full_match.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Find all potential special chars and escape them appropriately
    # This regex matches <, >, or & that are not part of an HTML tag
    text = re.sub(r'&(?![a-zA-Z]{2,6};|#[0-9]{1,4};)', '&amp;', text)
    text = re.sub(r'<(?![a-zA-Z/])', '&lt;', text)
    text = re.sub(r'(?<![^>])>', '&gt;', text)
    
    # Flatten nested bullet indentation (Telegram ignores it)
    # Convert multiple spaces/tabs at line start to single space
    text = re.sub(r'^[ \t]+', '  ', text, flags=re.MULTILINE)
    
    return text
