"""itch.io API client — game analytics via profile:games endpoint."""

import os
import httpx
from api._handler import BaseAPIHandler

ITCH_IO_API_KEY = os.getenv("ITCH_IO_API_KEY")


class ItchIOAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "itch_io"

    def _get_client(self):
        # itch.io uses API key in Authorization header
        return None  # Custom auth in requests

    def get_games(self) -> dict:
        """
        Get all games for the authenticated user.

        Returns:
            Dict with games array containing views, downloads, purchases, earnings
        """
        def _live() -> dict:
            if not ITCH_IO_API_KEY:
                return {"error": "ITCH_IO_API_KEY not set"}

            try:
                headers = {
                    "Authorization": f"Bearer {ITCH_IO_API_KEY}",
                }
                response = httpx.get(
                    "https://api.itch.io/profile/games",
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "games": data.get("games", []),
                }
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    return {"error": "Invalid itch.io API key"}
                if e.response.status_code == 403:
                    return {"error": "Insufficient permissions (need profile:games scope)"}
                return {"error": f"HTTP {e.response.status_code}: {e}"}
            except Exception as e:
                return {"error": str(e)}

        result = self.call("games", self.hash(), _live, stale_ok=True)

        # Add stale_notice to result
        from infra.cache import cache
        notice = cache.stale_notice(result)
        result["stale_notice"] = notice

        return result


# Module-level instance
itch_io_api = ItchIOAPIHandler()

# Module-level function for backwards compat
def get_games() -> dict:
    return itch_io_api.get_games()
