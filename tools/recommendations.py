"""Content recommendations tool — Steam + YouTube demand analysis."""

import os
import requests
from datetime import datetime, timedelta
from tools.youtube import _get_credentials
from googleapiclient.discovery import build

# Constants
STEAM_ID = os.getenv("STEAM_ID")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAMSPY_API = "https://steamspy.com/api.php"
STEAM_API = "https://api.steampowered.com"


def get_owned_games() -> list[dict]:
    """Get owned games from Steam Web API."""
    if not STEAM_API_KEY or not STEAM_ID:
        return []

    try:
        params = {
            "key": STEAM_API_KEY,
            "steamid": STEAM_ID,
            "include_appinfo": 1,
            "include_played_free_games": 1,
        }
        response = requests.get(
            f"{STEAM_API}/IPlayerService/GetOwnedGames/v0001/",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        games = []
        for game in data.get("response", {}).get("games", []):
            playtime_minutes = game.get("playtime_forever", 0)
            games.append({
                "appid": game.get("appid"),
                "name": game.get("name", "Unknown"),
                "playtime_hours": playtime_minutes / 60.0 if playtime_minutes else 0.0,
            })
        return games
    except Exception:
        return []


def get_steamspy_data(appid: int) -> dict:
    """Get SteamSpy data for a specific game."""
    try:
        params = {"request": "appdetails", "appid": appid}
        response = requests.get(STEAMSPY_API, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            "owners": data.get("owners", "0 .. 0"),
            "players_forever": data.get("players_forever", 0),
            "players_2weeks": data.get("players_2weeks", 0),
        }
    except Exception:
        return {}


def get_youtube_video_count(game_name: str, days: int = 30) -> dict:
    """Get YouTube video count and views for a game."""
    try:
        creds = _get_credentials()
        youtube = build("youtube", "v3", credentials=creds)

        published_after = (datetime.now() - timedelta(days=days)).isoformat() + "Z"
        query = f"{game_name} gameplay"

        search_response = youtube.search().list(
            q=query,
            type="video",
            publishedAfter=published_after,
            maxResults=5,
            order="viewCount",
            part="snippet"
        ).execute()

        video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]

        if not video_ids:
            return {"recent_upload_count": 0, "top_video_views": 0, "avg_views_top5": 0.0}

        videos_response = youtube.videos().list(
            part="statistics",
            id=",".join(video_ids)
        ).execute()

        view_counts = []
        for video in videos_response.get("items", []):
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
