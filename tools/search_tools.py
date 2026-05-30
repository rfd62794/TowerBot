"""Search and grounding tools — web, wiki, reddit, weather."""

import hashlib
from datetime import datetime
from tools.api.ddg_api import search_web, search_news
from tools.api.wikipedia_api import get_summary
from tools.api.reddit_api import search_reddit
from tools.api.weather_api import get_current_weather
from core.db import cache_tool_result, get_cached_tool_result, record_weather_day
from core.cache import cache
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
    params_hash = hashlib.md5(f"{query}_{max_results}".encode()).hexdigest()
    cached = get_cached_tool_result("web_search", params_hash)
    if cached:
        return cached

    results = search_web(query, max_results)
    result = {
        "query": query,
        "count": len(results),
        "results": results,
    }
    cache_tool_result("web_search", params_hash, result, ttl_hours=1)
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
    params_hash = hashlib.md5(f"news_{query}_{max_results}".encode()).hexdigest()
    cached = get_cached_tool_result("news_search", params_hash)
    if cached:
        return cached

    results = search_news(query, max_results)
    result = {
        "query": query,
        "count": len(results),
        "results": results,
    }
    cache_tool_result("news_search", params_hash, result, ttl_hours=0.5)
    return result


def wiki_lookup(topic: str) -> dict:
    """
    Look up a Wikipedia article summary.

    Args:
        topic: Topic to look up

    Returns:
        Dict with Wikipedia summary data
    """
    params_hash = hashlib.md5(f"wiki_{topic}".encode()).hexdigest()
    cached = get_cached_tool_result("wiki_lookup", params_hash)
    if cached:
        return cached

    result = get_summary(topic)
    cache_tool_result("wiki_lookup", params_hash, result, ttl_hours=24*7)
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
    params_hash = hashlib.md5(f"reddit_{query}_{subreddit}_{limit}".encode()).hexdigest()
    cached = get_cached_tool_result("reddit_search", params_hash)
    if cached:
        return cached

    results = search_reddit(query, subreddit, limit=limit)
    result = {
        "query": query,
        "subreddit": subreddit,
        "count": len(results),
        "results": results,
    }
    cache_tool_result("reddit_search", params_hash, result, ttl_hours=0.5)
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


# Module-level instance
_search = SearchTools()

# Backwards compat function
def get_weather() -> dict:
    return _search.get_weather()
