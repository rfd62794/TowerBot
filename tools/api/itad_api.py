"""IsThereAnyDeal API client — raw API calls only."""

import os
import requests

ITAD_API_KEY = os.getenv("ITAD_API_KEY")
ITAD_API = "https://api.isthereanydeal.com"


def lookup_game(name: str) -> dict:
    """Lookup game by name via ITAD search API."""
    if not ITAD_API_KEY:
        return {"error": "ITAD API key not configured"}
    
    try:
        headers = {"ITAD-API-Key": ITAD_API_KEY}
        params = {
            "title": name,
            "results": 1
        }
        response = requests.get(
            f"{ITAD_API}/games/search/v1",
            params=params,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return {"raw": data}
    except Exception as e:
        return {"error": str(e)}


def get_prices(game_ids: list[str], country: str = "US") -> dict:
    """Get prices for multiple games via ITAD API."""
    if not ITAD_API_KEY:
        return {"error": "ITAD API key not configured"}
    
    try:
        headers = {"ITAD-API-Key": ITAD_API_KEY}
        params = {"country": country}
        response = requests.post(
            f"{ITAD_API}/games/prices/v3",
            params=params,
            headers=headers,
            json=game_ids,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return {"raw": data}
    except Exception as e:
        return {"error": str(e)}
