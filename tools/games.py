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
ITAD_API_KEY = os.getenv("ITAD_API_KEY")
ITAD_API = "https://api.isthereanydeal.com"


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


def get_installed_games() -> dict:
    """
    Get currently installed games from Steam library.

    Returns games that are installed on the local machine,
    sorted by last played time (most recent first).

    Returns:
        Dict with count and list of installed games
    """
    owned = get_owned_games()

    # Filter to installed games (Steam API doesn't provide this directly,
    # so we return all owned games with playtime > 0 as a proxy for "installed")
    # This is a limitation of the Steam Web API - it doesn't expose installation status
    installed = [g for g in owned if g["playtime_hours"] > 0]

    # Sort by playtime (proxy for recency since last_played isn't always available)
    installed.sort(key=lambda x: x["playtime_hours"], reverse=True)

    return {
        "count": len(installed),
        "games": [
            {
                "name": g["name"],
                "appid": g["appid"],
                "playtime_hours": g["playtime_hours"],
            }
            for g in installed
        ],
    }


def get_sale_info(game_names: list[str]) -> dict:
    """
    Check current sale prices and historical lows for games via IsThereAnyDeal.

    Args:
        game_names: List of game names to check

    Returns:
        Dict with per-game sale information
    """
    if not ITAD_API_KEY:
        return {"error": "ITAD API key not configured"}

    results = {}
    game_ids = []

    # Step 1: Lookup all game IDs via search
    headers = {"ITAD-API-Key": ITAD_API_KEY}
    for game_name in game_names:
        try:
            search_params = {
                "title": game_name,
                "results": 1
            }
            search_response = requests.get(
                f"{ITAD_API}/games/search/v1",
                params=search_params,
                headers=headers,
                timeout=10
            )
            search_response.raise_for_status()
            search_data = search_response.json()

            if search_data and isinstance(search_data, list) and len(search_data) > 0:
                game_id = search_data[0].get("id")
                if game_id:
                    game_ids.append(game_id)
                    results[game_name] = {"id": game_id}
                else:
                    results[game_name] = {"error": "not found"}
            else:
                results[game_name] = {"error": "not found"}
        except Exception as e:
            results[game_name] = {"error": str(e)}

    # Step 2: Get prices for all found games (batch request)
    if game_ids:
        try:
            prices_response = requests.post(
                f"{ITAD_API}/games/prices/v3",
                params={"country": "US"},
                headers=headers,
                json=game_ids,
                timeout=10
            )
            prices_response.raise_for_status()
            prices_data = prices_response.json()

            # Map game IDs to price data
            price_map = {}
            for price_info in prices_data:
                game_id = price_info.get("id")
                if game_id:
                    price_map[game_id] = price_info

            # Merge price data into results
            for game_name, data in results.items():
                if "error" in data:
                    continue
                game_id = data.get("id")
                if game_id in price_map:
                    price_info = price_map[game_id]
                    deals = price_info.get("deals", [])
                    history_low = price_info.get("historyLow", {})

                    # Find best current deal
                    best_deal = None
                    for deal in deals:
                        if deal.get("price") and deal.get("cut"):
                            if best_deal is None or deal["cut"] > best_deal["cut"]:
                                best_deal = deal

                    if best_deal:
                        results[game_name] = {
                            "current_price": best_deal.get("price", {}).get("amount", 0.0),
                            "current_discount_pct": best_deal.get("cut", 0),
                            "historical_low": history_low.get("price", {}).get("amount", 0.0),
                            "on_sale": best_deal.get("cut", 0) > 0,
                            "store_name": best_deal.get("shop", {}).get("name", "Unknown"),
                            "store_url": best_deal.get("url", ""),
                        }
                    else:
                        results[game_name] = {
                            "current_price": history_low.get("price", {}).get("amount", 0.0),
                            "current_discount_pct": 0,
                            "historical_low": history_low.get("price", {}).get("amount", 0.0),
                            "on_sale": False,
                            "store_name": "Steam",
                            "store_url": "",
                        }
                else:
                    results[game_name] = {"error": "no price data"}

        except Exception as e:
            for game_name in results:
                if "error" not in results[game_name]:
                    results[game_name] = {"error": f"price fetch failed: {str(e)}"}

    return {"games": results}
