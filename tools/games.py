"""Game metrics tool — per-game deep dive with Steam + YouTube data."""

import os
import json
import requests
import difflib
from datetime import datetime, timedelta
from pathlib import Path
from tools.recommendations import get_owned_games
from tools.youtube import _get_credentials
from googleapiclient.discovery import build

# Constants
STEAM_ID = os.getenv("STEAM_ID")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAMSPY_API = "https://steamspy.com/api.php"
STEAM_API = "https://api.steampowered.com"
STEAM_CATALOG_CACHE = Path("config/steam_catalog.json")


def get_steam_catalog() -> list[dict]:
    """Get Steam catalog with caching."""
    # Check cache (valid for 7 days)
    if STEAM_CATALOG_CACHE.exists():
        try:
            with open(STEAM_CATALOG_CACHE, "r") as f:
                cache_data = json.load(f)
                cache_time = datetime.fromisoformat(cache_data.get("timestamp", "1970-01-01"))
                if (datetime.now() - cache_time).total_seconds() < 604800:  # 7 days
                    return cache_data.get("apps", [])
        except (IOError, json.JSONDecodeError):
            pass

    # Fetch fresh catalog
    try:
        response = requests.get(
            f"{STEAM_API}/ISteamApps/GetAppList/v2/",
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        apps = data.get("applist", {}).get("apps", [])

        # Cache with timestamp
        STEAM_CATALOG_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(STEAM_CATALOG_CACHE, "w") as f:
            json.dump({"timestamp": datetime.now().isoformat(), "apps": apps}, f)

        return apps
    except Exception:
        return []


def resolve_appid(game_name: str) -> dict | None:
    """
    Resolve game name to AppID with fuzzy matching.

    Priority:
    1. Exact match in owned library
    2. Fuzzy match in owned library
    3. Exact match in Steam catalog
    4. Fuzzy match in Steam catalog

    Returns:
        {"appid": int, "name": str, "source": "owned"|"catalog"} or None
    """
    # Step 1: Search owned library first
    owned = get_owned_games()
    for game in owned:
        if game_name.lower() in game["name"].lower():
            return {"appid": game["appid"], "name": game["name"], "source": "owned"}

    # Step 2: Fuzzy match owned library
    names = [g["name"] for g in owned]
    matches = difflib.get_close_matches(game_name, names, n=1, cutoff=0.6)
    if matches:
        match = next(g for g in owned if g["name"] == matches[0])
        return {"appid": match["appid"], "name": match["name"], "source": "owned"}

    # Step 3: Full Steam catalog search
    catalog = get_steam_catalog()
    for app in catalog:
        if game_name.lower() in app.get("name", "").lower():
            return {"appid": app["appid"], "name": app["name"], "source": "catalog"}

    # Step 4: Fuzzy match catalog
    catalog_names = [app.get("name", "") for app in catalog]
    matches = difflib.get_close_matches(game_name, catalog_names, n=1, cutoff=0.7)
    if matches:
        match = next(app for app in catalog if app.get("name") == matches[0])
        return {"appid": match["appid"], "name": match["name"], "source": "catalog"}

    return None


def get_steamspy_info(appid: int) -> dict:
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
            return {"recent_count": 0, "top_views": 0, "gap_signal": "none"}

        videos_response = youtube.videos().list(
            part="statistics",
            id=",".join(video_ids)
        ).execute()

        view_counts = []
        for video in videos_response.get("items", []):
            views = int(video["statistics"].get("viewCount", 0))
            view_counts.append(views)

        if view_counts:
            recent_count = len(view_counts)
            top_views = max(view_counts)

            # Gap signal logic
            if recent_count == 0:
                gap_signal = "none"
            elif recent_count < 5:
                gap_signal = "low"
            elif recent_count < 20:
                gap_signal = "medium"
            else:
                gap_signal = "high"

            return {
                "recent_count": recent_count,
                "top_views": top_views,
                "gap_signal": gap_signal,
            }
        return {"recent_count": 0, "top_views": 0, "gap_signal": "none"}
    except Exception:
        return {"recent_count": 0, "top_views": 0, "gap_signal": "none"}


def get_game_metrics(game_name: str) -> dict:
    """
    Get detailed metrics for a specific game by name.

    Automatically resolves AppID from game name using fuzzy matching.
    Combines SteamSpy market data, your personal playtime, and YouTube
    coverage to provide a comprehensive view of a game's content potential.

    Args:
        game_name: Name of the game (e.g. "Raccoin", "Duckov")

    Returns:
        Dict with game metrics, playtime, player counts, YouTube coverage,
        content gap signal, and verdict
    """
    # Resolve AppID
    resolved = resolve_appid(game_name)
    if not resolved:
        return {"error": f"Game not found: {game_name}"}

    appid = resolved["appid"]
    name = resolved["name"]

    # Get your playtime
    owned = get_owned_games()
    your_playtime = 0.0
    for game in owned:
        if game["appid"] == appid:
            your_playtime = game["playtime_hours"]
            break

    # Get SteamSpy data
    steamspy_data = get_steamspy_info(appid)

    # Get YouTube coverage
    yt_data = get_youtube_coverage(name)

    # Calculate review score
    positive = steamspy_data.get("positive_reviews", 0)
    negative = steamspy_data.get("negative_reviews", 0)
    total = positive + negative
    review_score = (positive / total * 100.0) if total > 0 else None

    # Verdict logic
    gap = yt_data.get("gap_signal", "none")
    if gap == "none" and your_playtime > 5:
        verdict = "Strong opportunity — underserved content, you know the game."
    elif gap == "low" and your_playtime > 5:
        verdict = "Good opportunity — limited competition."
    elif gap == "high":
        verdict = "Saturated — hard to surface organically."
    elif your_playtime < 1:
        verdict = "Insufficient playtime to speak to this."
    else:
        verdict = "Moderate opportunity — worth considering."

    return {
        "name": name,
        "appid": appid,
        "your_playtime_hours": your_playtime,
        "steam_owners": steamspy_data.get("owners", "0 .. 0"),
        "players_2weeks": steamspy_data.get("players_2weeks", 0),
        "review_score": review_score,
        "youtube_recent_uploads": yt_data.get("recent_count", 0),
        "youtube_top_views": yt_data.get("top_views", 0),
        "content_gap": gap,
        "verdict": verdict,
    }
