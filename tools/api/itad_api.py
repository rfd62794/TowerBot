"""IsThereAnyDeal API client — raw API calls only."""

import os
import requests
from tools.api._handler import BaseAPIHandler

ITAD_API_KEY = os.getenv("ITAD_API_KEY")
ITAD_API = "https://api.isthereanydeal.com"


class ITADAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "itad"
    API_KEY = os.getenv("ITAD_API_KEY")
    BASE_URL = "https://api.isthereanydeal.com"

    def _get_client(self):
        return None  # HTTP only

    def lookup_game(self, name: str) -> dict:
        """Lookup game by name via ITAD search API."""
        params_hash = self.hash(name.lower())

        def _live():
            if not self.API_KEY:
                return {"error": "ITAD API key not configured"}

            headers = {"ITAD-API-Key": self.API_KEY}
            params = {
                "title": name,
                "results": 1
            }
            response = requests.get(
                f"{self.BASE_URL}/games/search/v1",
                params=params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return {"raw": data}

        return self.call("lookup", params_hash, _live, stale_ok=True)

    def get_prices(self, game_ids: list[str], country: str = "US") -> dict:
        """Get prices for multiple games via ITAD API."""
        params_hash = self.hash(tuple(sorted(game_ids)), country)

        def _live():
            if not self.API_KEY:
                return {"error": "ITAD API key not configured"}

            headers = {"ITAD-API-Key": self.API_KEY}
            params = {"country": country}
            response = requests.post(
                f"{self.BASE_URL}/games/prices/v3",
                params=params,
                headers=headers,
                json=game_ids,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return {"raw": data}

        return self.call("prices", params_hash, _live, stale_ok=True)


# Module-level instance
itad_api = ITADAPIHandler()


# Backwards compat
def lookup_game(name: str) -> dict:
    return itad_api.lookup_game(name)


def get_prices(game_ids: list[str], country: str = "US") -> dict:
    return itad_api.get_prices(game_ids, country)
