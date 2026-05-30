"""Content recommendations tool — Steam + YouTube demand analysis."""

from datetime import datetime, timedelta
from tools.api.steam_api import get_game_library
from tools.api.steamspy_api import get_app_details
from tools.api.youtube_api import search_youtube, get_video_statistics


def get_owned_games() -> list[dict]:
    """Get owned games from Steam Web API."""
    library_result = get_game_library()
    if "error" in library_result:
        return []
    
    return library_result["raw"]


def get_steamspy_data(appid: int) -> dict:
    """Get SteamSpy data for a specific game."""
    result = get_app_details(appid)
    if "error" in result:
        return {}
    
    data = result["raw"]
    return {
        "owners": data.get("owners", "0 .. 0"),
        "players_forever": data.get("players_forever", 0),
        "players_2weeks": data.get("players_2weeks", 0),
    }


def get_youtube_video_count(game_name: str, days: int = 30) -> dict:
    """Get YouTube video count and views for a game."""
    try:
        api_response = search_youtube(f"{game_name} gameplay", days, max_results=5)
        if "error" in api_response:
            return {"recent_upload_count": 0, "top_video_views": 0, "avg_views_top5": 0.0}

        response = api_response["raw"]
        video_ids = [item["id"]["videoId"] for item in response.get("items", [])]

        if not video_ids:
            return {"recent_upload_count": 0, "top_video_views": 0, "avg_views_top5": 0.0}

        stats_response = get_video_statistics(video_ids)
        if "error" in stats_response:
            return {"recent_upload_count": len(video_ids), "top_video_views": 0, "avg_views_top5": 0.0}

        stats = stats_response["raw"]
        view_counts = []
        for video in stats.get("items", []):
            views = int(video["statistics"].get("viewCount", 0))
            view_counts.append(views)

        if view_counts:
            return {
                "recent_upload_count": len(view_counts),
                "top_video_views": max(view_counts),
                "avg_views_top5": sum(view_counts) / len(view_counts),
            }
        return {"recent_upload_count": 0, "top_video_views": 0, "avg_views_top5": 0.0}
    except Exception:
        return {"recent_upload_count": 0, "top_video_views": 0, "avg_views_top5": 0.0}


def score_game(game: dict, steam_data: dict, yt_data: dict) -> float:
    """Calculate composite score for a game."""
    playtime_score = min(game["playtime_hours"] / 10, 5.0)

    demand_score = 0.0
    if yt_data.get("recent_upload_count", 0) > 0:
        demand_score = min(yt_data.get("top_video_views", 0) / 100000, 5.0)

    gap_bonus = 0.0
    if yt_data.get("recent_upload_count", 0) < 3:
        gap_bonus = 2.0

    composite = (playtime_score * 0.4) + (demand_score * 0.4) + (gap_bonus * 0.2)
    return round(composite, 3)


def get_content_recommendations(limit: int = 5, min_playtime: float = 1.0) -> dict:
    """
    Get game recommendations for content recording.

    Combines Steam playtime with YouTube demand signals to rank games
    by content opportunity.

    Args:
        limit: Maximum number of recommendations to return
        min_playtime: Minimum playtime hours threshold

    Returns:
        Dict with count and list of recommendations
    """
    games = get_owned_games()
    games = [g for g in games if g["playtime_hours"] >= min_playtime]
    games.sort(key=lambda x: x["playtime_hours"], reverse=True)

    results = []
    for game in games[:20]:  # Top 20 by playtime
        steam_data = get_steamspy_data(game["appid"])
        yt_data = get_youtube_video_count(game["name"])

        game["composite_score"] = score_game(game, steam_data, yt_data)
        game["content_demand_score"] = yt_data.get("top_video_views", 0) / 100000
        game["recent_upload_count"] = yt_data.get("recent_upload_count", 0)
        results.append(game)

    results.sort(key=lambda x: x["composite_score"], reverse=True)

    return {
        "count": min(limit, len(results)),
        "recommendations": results[:limit]
    }
