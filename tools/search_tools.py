"""Search and grounding tools — web, wiki, reddit, weather."""

import hashlib
from datetime import datetime
from tools.api.ddg_api import search_web, search_news
from tools.api.wikipedia_api import get_summary
from tools.api.reddit_api import search_reddit
from tools.api.weather_api import get_current_weather
from core.db import record_weather_day
from tools._tool import BaseTool


def web_search(query: str, max_results: int = 5) -> dict:
    """
    Search the web via DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum results to return

    Returns:
        Dict with query, count, and results
    """
    results = search_web(query, max_results)
    result = {
        "query": query,
        "count": len(results),
        "results": results,
    }
    return result


def news_search(query: str, max_results: int = 5) -> dict:
    """
    Search recent news via DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum results to return

    Returns:
        Dict with query, count, and results
    """
    results = search_news(query, max_results)
    result = {
        "query": query,
        "count": len(results),
        "results": results,
    }
    return result


def wiki_lookup(topic: str) -> dict:
    """
    Look up a Wikipedia article summary.

    Args:
        topic: Topic to look up

    Returns:
        Dict with Wikipedia summary data
    """
    result = get_summary(topic)
    return result


def reddit_search(query: str, subreddit: str = None, limit: int = 10) -> dict:
    """
    Search Reddit posts.

    Args:
        query: Search query
        subreddit: Optional subreddit to search within
        limit: Maximum results to return

    Returns:
        Dict with query, subreddit, count, and results
    """
    results = search_reddit(query, subreddit, limit=limit)
    result = {
        "query": query,
        "subreddit": subreddit,
        "count": len(results),
        "results": results,
    }
    return result


class SearchTools(BaseTool):
    def get_weather(self) -> dict:
        """
        Get current weather for South Florida.

        Returns:
            Dict with current weather data
        """
        raw = get_current_weather()

        if raw.get("_live_failed"):
            return self.error("Weather unavailable", code="api_failed")

        # Record to weather history if fresh
        if not raw.get("_stale"):
            record_weather_day(
                datetime.now().strftime("%Y-%m-%d"),
                raw.get("temp_f", 0),
                raw.get("condition", ""),
                raw.get("wind_mph", 0),
            )

        return self.success(
            {
                "temp_f": raw.get("temp_f"),
                "condition": raw.get("condition"),
                "wind_mph": raw.get("wind_mph"),
                "precipitation_mm": raw.get("precipitation_mm"),
            },
            stale_result=raw,
        )

    def web_search(self, query: str, max_results: int = 5) -> dict:
        """
        Search the web via DuckDuckGo.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            Dict with query, count, and results
        """
        raw = search_web(query, max_results)
        if raw.get("_live_failed"):
            return self.error("Web search unavailable", code="api_failed")
        results = raw.get("results", [])
        return self.success({
            "query": query,
            "count": len(results),
            "results": results
        }, stale_result=raw)

    def news_search(self, query: str, max_results: int = 5) -> dict:
        """
        Search recent news via DuckDuckGo.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            Dict with query, count, and results
        """
        raw = search_news(query, max_results)
        if raw.get("_live_failed"):
            return self.error("News search unavailable", code="api_failed")
        results = raw.get("results", [])
        return self.success({
            "query": query,
            "count": len(results),
            "results": results
        }, stale_result=raw)

    def wiki_lookup(self, topic: str) -> dict:
        """
        Look up a Wikipedia article summary.

        Args:
            topic: Topic to look up

        Returns:
            Dict with Wikipedia summary data
        """
        raw = get_summary(topic)
        if raw.get("_live_failed"):
            return self.error("Wikipedia unavailable", code="api_failed")
        # found=False is valid, not an error
        return self.success({
            "found": raw.get("found", False),
            "title": raw.get("title", topic),
            "description": raw.get("description", ""),
            "extract": raw.get("extract", "")
        }, stale_result=raw)

    def reddit_search(self, query: str, subreddit: str = None, limit: int = 10) -> dict:
        """
        Search Reddit posts.

        Args:
            query: Search query
            subreddit: Optional subreddit to search within
            limit: Maximum results to return

        Returns:
            Dict with query, subreddit, count, and results
        """
        raw = search_reddit(query, subreddit, limit=limit)
        if raw.get("_live_failed"):
            return self.error("Reddit search unavailable", code="api_failed")
        results = raw.get("results", [])
        return self.success({
            "query": query,
            "subreddit": subreddit,
            "count": len(results),
            "results": results
        }, stale_result=raw)


# Module-level instance
_search = SearchTools()

# Backwards compat functions
def get_weather() -> dict:
    return _search.get_weather()

def web_search(query: str, max_results: int = 5) -> dict:
    return _search.web_search(query, max_results)

def news_search(query: str, max_results: int = 5) -> dict:
    return _search.news_search(query, max_results)

def wiki_lookup(topic: str) -> dict:
    return _search.wiki_lookup(topic)

def reddit_search(query: str, subreddit: str = None, limit: int = 10) -> dict:
    return _search.reddit_search(query, subreddit, limit)
