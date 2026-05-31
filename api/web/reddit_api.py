"""Reddit API client — raw API calls only."""

import os
import requests
import base64
from api._handler import BaseAPIHandler

HEADERS = {
    "User-Agent": "PrivyBot/1.0 by /u/FamiliarAnxiety9"
}


class RedditAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "reddit"
    BASE_URL = "https://www.reddit.com"
    HEADERS = {
        "User-Agent": "PrivyBot/1.0 by /u/FamiliarAnxiety9"
    }

    def __init__(self):
        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self._access_token = None

    def _get_oauth_token(self) -> str | None:
        """Get OAuth access token if credentials are configured."""
        if not self.client_id or not self.client_secret:
            return None

        if self._access_token:
            return self._access_token

        try:
            auth = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            
            response = requests.post(
                "https://www.reddit.com/api/v1/access_token",
                headers={
                    "Authorization": f"Basic {auth}",
                    "User-Agent": self.HEADERS["User-Agent"]
                },
                data={"grant_type": "client_credentials"},
                timeout=10
            )
            response.raise_for_status()
            self._access_token = response.json().get("access_token")
            return self._access_token
        except Exception:
            return None

    def _get_headers(self) -> dict:
        """Get headers with OAuth token if available."""
        headers = self.HEADERS.copy()
        token = self._get_oauth_token()
        if token:
            headers["Authorization"] = f"bearer {token}"
        return headers

    def _get_client(self):
        return None  # HTTP only

    def search_reddit(self, query: str, subreddit: str = None, sort: str = "relevance", limit: int = 10) -> dict:
        """
        Search Reddit posts.

        Args:
            query: Search query
            subreddit: Optional subreddit to search within
            sort: Sort order (relevance, new, hot, top)
            limit: Maximum results to return

        Returns:
            Dict with results list, query, subreddit
        """
        params_hash = self.hash(query, subreddit, sort, limit)

        def _live() -> dict:
            if subreddit:
                url = f"{self.BASE_URL}/r/{subreddit}/search.json"
            else:
                url = f"{self.BASE_URL}/search.json"

            params = {
                "q": query,
                "sort": sort,
                "limit": limit,
                "restrict_sr": bool(subreddit)
            }

            response = requests.get(url, headers=self._get_headers(), params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            posts = []
            for post in data.get("data", {}).get("children", []):
                post_data = post.get("data", {})
                posts.append({
                    "title": post_data.get("title", ""),
                    "score": post_data.get("score", 0),
                    "url": post_data.get("url", ""),
                    "subreddit": post_data.get("subreddit", ""),
                    "num_comments": post_data.get("num_comments", 0),
                    "created_utc": post_data.get("created_utc", 0),
                })

            return {
                "results": posts,
                "query": query,
                "subreddit": subreddit
            }

        return self.call("search", params_hash, _live, stale_ok=True)


# Module-level instance
reddit_api = RedditAPIHandler()


# Backwards compat
def search_reddit(query: str, subreddit: str = None, sort: str = "relevance", limit: int = 10) -> list[dict]:
    result = reddit_api.search_reddit(query, subreddit, sort, limit)
    return result.get("results", [])
