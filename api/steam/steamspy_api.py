"""SteamSpy API client — raw API calls only."""

import os
import requests
from api._handler import BaseAPIHandler

STEAMSPY_API = "https://steamspy.com/api.php"


class SteamSpyAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "steamspy"
    BASE_URL = "https://steamspy.com/api.php"

    def _get_client(self):
        return None  # HTTP only

    def get_app_details(self, appid: int) -> dict:
        """Get SteamSpy data for a specific game."""
        params_hash = self.hash(appid)

        def _live():
            params = {"request": "appdetails", "appid": appid}
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return {"raw": data}

        return self.call("app_details", params_hash, _live, stale_ok=True)


# Module-level instance
steamspy_api = SteamSpyAPIHandler()


# Backwards compat
def get_app_details(appid: int) -> dict:
    return steamspy_api.get_app_details(appid)
