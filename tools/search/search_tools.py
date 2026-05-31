"""Search and grounding tools — web, wiki, reddit, weather."""

import hashlib
from datetime import datetime
from api.web.ddg_api import ddg_api
from api.web.wikipedia_api import wikipedia_api
from api.web.reddit_api import reddit_api
from api.weather.weather_api import get_current_weather, weather_api
from infra.db import record_weather_day
from tools._tool import BaseTool


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

    def get_weather_forecast(self, days: int = 3) -> dict:
        """
        Get weather forecast for South Florida.

        Args:
            days: Number of forecast days (1-7, default 3)

        Returns:
            Dict with daily forecast data
        """
        from api.weather.weather_api import WMO_CODES

        raw = weather_api.get_forecast(days)

        if raw.get("_live_failed") or "error" in raw:
            return self.error("Weather forecast unavailable", code="api_failed")

        daily = raw.get("daily", {})
        times = daily.get("time", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_probability_max", [])
        codes = daily.get("weathercode", [])

        forecast = []
        for i, date_str in enumerate(times):
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            forecast.append({
                "date": date_str,
                "day_of_week": dt.strftime("%A"),
                "high_f": highs[i] if i < len(highs) else None,
                "low_f": lows[i] if i < len(lows) else None,
                "precipitation_pct": precip[i] if i < len(precip) else None,
                "condition": WMO_CODES.get(
                    int(codes[i]) if i < len(codes) else 0, "Unknown"
                ),
            })

        return self.success({"days": forecast, "count": len(forecast)},
                            stale_result=raw)

    def web_search(self, query: str, max_results: int = 5) -> dict:
        """
        Search the web via DuckDuckGo.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            Dict with query, count, and results
        """
        raw = ddg_api.search_web(query, max_results)
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
        raw = ddg_api.search_news(query, max_results)
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
        raw = wikipedia_api.get_summary(topic)
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
        raw = reddit_api.search_reddit(query, subreddit, limit=limit)
        if raw.get("_live_failed"):
            return self.error("Reddit search unavailable", code="api_failed")
        results = raw.get("results", [])
        return self.success({
            "query": query,
            "subreddit": subreddit,
            "count": len(results),
            "results": results
        }, stale_result=raw)

    def fetch_url(self, url: str, max_chars: int = 3000) -> dict:
        """
        Fetch and read the full text content of a web page.

        Args:
            url: The full URL to fetch including https:// prefix
            max_chars: Maximum characters to return (default 3000)

        Returns:
            Dict with url, title, content, char_count, truncated
        """
        from api.web.fetch_api import fetch_api

        raw = fetch_api.fetch_url(url, max_chars)

        if raw.get("_live_failed"):
            return self.error(f"Could not fetch: {url}", code="api_failed")

        if "error" in raw:
            return self.error(raw["error"])

        return self.success({
            "url": url,
            "title": raw.get("title", ""),
            "content": raw.get("content", ""),
            "char_count": raw.get("char_count", 0),
            "truncated": raw.get("truncated", False)
        }, stale_result=raw)


# Module-level instance
_search = SearchTools()


# Backwards compat functions
def web_search(query: str, max_results: int = 5) -> dict:
    """
    Search the web via DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum results to return

    Returns:
        Dict with query, count, and results
    """
    return _search.web_search(query, max_results)


def news_search(query: str, max_results: int = 5) -> dict:
    """
    Search recent news via DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum results to return

    Returns:
        Dict with query, count, and results
    """
    return _search.news_search(query, max_results)


def wiki_lookup(topic: str) -> dict:
    """
    Look up a Wikipedia article summary.

    Args:
        topic: Topic to look up

    Returns:
        Dict with Wikipedia summary data
    """
    return _search.wiki_lookup(topic)


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
    return _search.reddit_search(query, subreddit, limit)


def get_weather() -> dict:
    return _search.get_weather()


def get_weather_forecast(days: int = 3) -> dict:
    """
    Get weather forecast for South Florida.

    Args:
        days: Number of forecast days (1-7, default 3)

    Returns:
        Dict with daily forecast data
    """
    return _search.get_weather_forecast(days)


def fetch_url(url: str, max_chars: int = 3000) -> dict:
    """
    Fetch and read the full text content of a web page.

    Args:
        url: The full URL to fetch including https:// prefix
        max_chars: Maximum characters to return (default 3000)

    Returns:
        Dict with url, title, content, char_count, truncated
    """
    return _search.fetch_url(url, max_chars)
