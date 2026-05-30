"""Steam API client — raw API calls only."""

import os
import requests

STEAM_ID = os.getenv("STEAM_ID")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
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
        return {"raw": data}
    except Exception as e:
        return {"error": str(e)}


def get_game_library() -> list[dict]:
    """Get game library with playtime data."""
    result = get_owned_games()
    if "error" in result:
        return result
    
    data = result["raw"]
    games = []
    for game in data.get("response", {}).get("games", []):
        playtime_minutes = game.get("playtime_forever", 0)
        games.append({
            "appid": game.get("appid"),
            "name": game.get("name", "Unknown"),
            "playtime_hours": playtime_minutes / 60.0 if playtime_minutes else 0.0,
        })
    return {"raw": games}


def resolve_appid_from_library(name: str) -> dict:
    """Resolve AppID from game name in owned library."""
    result = get_game_library()
    if "error" in result:
        return result
    
    games = result["raw"]
    for game in games:
        if name.lower() in game["name"].lower():
            return {"raw": {"appid": game["appid"], "name": game["name"]}}
    
    return {"error": "Game not found in library"}
