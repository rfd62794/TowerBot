"""DuckDuckGo search API client — raw API calls only."""

from ddgs import DDGS
from api._handler import BaseAPIHandler


class DDGAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "ddg"

    def _get_client(self):
        return None  # no auth needed

    def search_web(self, query: str, max_results: int = 5) -> dict:
        """
        Search DuckDuckGo for web results.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            Dict with results list and query
        """
        params_hash = self.hash(query, max_results)

        def _live() -> dict:
            results = []
            ddgs = DDGS()
            for result in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "body": result.get("body", ""),
                })
            return {
                "results": results,
                "query": query
            }

        return self.call("web_search", params_hash, _live, stale_ok=True)

    def search_news(self, query: str, max_results: int = 5) -> dict:
        """
        Search DuckDuckGo for news results.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            Dict with results list and query
        """
        params_hash = self.hash(query, max_results)

        def _live() -> dict:
            results = []
            ddgs = DDGS()
            for result in ddgs.news(query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "body": result.get("body", ""),
                    "date": result.get("date", ""),
                    "source": result.get("source", ""),
                })
            return {
                "results": results,
                "query": query
            }

        return self.call("news_search", params_hash, _live, stale_ok=True)


# Module-level instance
ddg_api = DDGAPIHandler()


# Backwards compat
def search_web(query: str, max_results: int = 5) -> list[dict]:
    result = ddg_api.search_web(query, max_results)
    return result.get("results", [])


def search_news(query: str, max_results: int = 5) -> list[dict]:
    result = ddg_api.search_news(query, max_results)
    return result.get("results", [])
