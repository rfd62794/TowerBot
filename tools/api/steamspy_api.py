"""SteamSpy API client — raw API calls only."""

import os
import requests

STEAMSPY_API = "https://steamspy.com/api.php"


def get_app_details(appid: int) -> dict:
    """Get SteamSpy data for a specific game."""
    try:
        params = {"request": "appdetails", "appid": appid}
        response = requests.get(STEAMSPY_API, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {"raw": data}
    except Exception as e:
        return {"error": str(e)}
