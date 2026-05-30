"""Wikipedia API client — raw API calls only."""

import requests
from tools.api._handler import BaseAPIHandler

WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1"


class WikipediaAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "wikipedia"
    BASE_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"

    def _get_client(self):
        return None  # no auth

    def get_summary(self, topic: str) -> dict:
        """
        Get Wikipedia article summary for a topic.

        Args:
            topic: Topic to look up (article title)

        Returns:
            Dict with title, description, extract, found status
        """
        params_hash = self.hash(topic.lower().strip())

        def _live() -> dict:
            url = f"{WIKIPEDIA_API}/page/summary/{topic}"
            response = requests.get(url, timeout=10)

            if response.status_code == 404:
                return {
                    "found": False,
                    "title": topic,
                }

            response.raise_for_status()
            data = response.json()

            return {
                "title": data.get("title", topic),
                "description": data.get("description", ""),
                "extract": data.get("extract", ""),
                "found": True,
            }

        return self.call("summary", params_hash, _live, stale_ok=True)


# Module-level instance
wikipedia_api = WikipediaAPIHandler()


# Backwards compat
def get_summary(topic: str) -> dict:
    return wikipedia_api.get_summary(topic)
