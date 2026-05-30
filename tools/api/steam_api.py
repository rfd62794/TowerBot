"""Steam API client — raw API calls only."""

import os
import requests
from tools.api._handler import BaseAPIHandler

STEAM_ID = os.getenv("STEAM_ID")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAM_API = "https://api.steampowered.com"


class SteamAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "steam"
    BASE_URL = "https://api.steampowered.com"
    STEAM_KEY = os.getenv("STEAM_API_KEY")
    STEAM_ID = os.getenv("STEAM_ID")

    def _get_client(self):
        return None  # Steam uses HTTP, no client

    def get_owned_games(self) -> dict:
        """Raw Steam API call — internal use only."""
        def _live():
            if not self.STEAM_KEY or not self.STEAM_ID:
                return {"raw": []}

            params = {
                "key": self.STEAM_KEY,
                "steamid": self.STEAM_ID,
                "include_appinfo": 1,
                "include_played_free_games": 1,
            }
            response = requests.get(
                f"{self.BASE_URL}/IPlayerService/GetOwnedGames/v0001/",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return {"raw": data}

        try:
            return _live()
        except Exception as e:
            return {"error": str(e)}

    def get_game_library(self) -> dict:
        """Transformed library — cached."""
        def _live():
            raw = self.get_owned_games()
            if "error" in raw:
                raise Exception(raw["error"])

            data = raw["raw"]
            games = []
            for game in data.get("response", {}).get("games", []):
                playtime_minutes = game.get("playtime_forever", 0)
                games.append({
                    "appid": game.get("appid"),
                    "name": game.get("name", "Unknown"),
                    "playtime_hours": playtime_minutes / 60.0 if playtime_minutes else 0.0,
                })
            return {"raw": games}

        return self.call("library", self.hash(), _live, stale_ok=True)

    # UNUSED — not migrated to BaseAPIHandler
    def resolve_appid_from_library(self, name: str) -> dict:
        """Resolve AppID from game name in owned library."""
        result = self.get_game_library()
        if "error" in result:
            return result

        games = result["raw"]
        for game in games:
            if name.lower() in game["name"].lower():
                return {"raw": {"appid": game["appid"], "name": game["name"]}}

        return {"error": "Game not found in library"}


# Module-level instance
steam_api = SteamAPIHandler()


# Backwards compat
def get_owned_games() -> list[dict]:
    return steam_api.get_owned_games()


def get_game_library() -> list[dict]:
    return steam_api.get_game_library()


def resolve_appid_from_library(name: str) -> dict:
    return steam_api.resolve_appid_from_library(name)
