"""Game metrics tool — per-game deep dive with Steam + YouTube data."""

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
            "positive_reviews": data.get("positive", 0),
            "negative_reviews": data.get("negative", 0),
        }
    except Exception:
        return {}


def get_steam_playtime(appid: int) -> dict:
    """Get your playtime for a specific game from Steam API."""
    if not STEAM_API_KEY or not STEAM_ID:
        return {"playtime_hours": 0.0, "name": "Unknown"}

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

        for game in data.get("response", {}).get("games", []):
            if game.get("appid") == appid:
                playtime_minutes = game.get("playtime_forever", 0)
                return {
                    "playtime_hours": playtime_minutes / 60.0 if playtime_minutes else 0.0,
                    "name": game.get("name", "Unknown"),
                }
        return {"playtime_hours": 0.0, "name": "Unknown"}
    except Exception:
        return {"playtime_hours": 0.0, "name": "Unknown"}


def get_youtube_coverage(game_name: str, days: int = 30) -> dict:
    """Get YouTube coverage data for a game."""
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


def get_game_metrics(appid: int) -> dict:
    """
    Get detailed metrics for a specific game by Steam AppID.

    Combines SteamSpy market data, your personal playtime, and YouTube
    coverage to provide a comprehensive view of a game's content potential.

    Args:
        appid: Steam AppID of the game

    Returns:
        Dict with game name, playtime, player counts, reviews, and YouTube coverage
    """
    steam_data = get_steam_playtime(appid)
    steamspy_data = get_steamspy_data(appid)
    yt_data = get_youtube_coverage(steam_data.get("name", ""), days=30)

    # Calculate review score
    positive = steamspy_data.get("positive_reviews", 0)
    negative = steamspy_data.get("negative_reviews", 0)
    total = positive + negative
    review_score = (positive / total * 100.0) if total > 0 else None

    return {
        "appid": appid,
        "name": steam_data.get("name", "Unknown"),
        "playtime_hours": steam_data.get("playtime_hours", 0.0),
        "players_2weeks": steamspy_data.get("players_2weeks", 0),
        "players_forever": steamspy_data.get("players_forever", 0),
        "owners_estimate": steamspy_data.get("owners", "0 .. 0"),
        "review_score": review_score,
        "positive_reviews": positive,
        "negative_reviews": negative,
        "youtube_recent_uploads": yt_data.get("recent_upload_count", 0),
        "youtube_top_views": yt_data.get("top_video_views", 0),
        "youtube_avg_views": yt_data.get("avg_views_top5", 0.0),
    }
