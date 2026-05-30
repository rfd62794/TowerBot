"""Search and grounding tools — web, wiki, reddit, weather."""

from tools.api.ddg_api import search_web, search_news
from tools.api.wikipedia_api import get_summary
from tools.api.reddit_api import search_reddit
from tools.api.weather_api import get_current_weather


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
    return {
        "query": query,
        "count": len(results),
        "results": results,
    }


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
    return {
        "query": query,
        "count": len(results),
        "results": results,
    }


def wiki_lookup(topic: str) -> dict:
    """
    Look up a Wikipedia article summary.

    Args:
        topic: Topic to look up

    Returns:
        Dict with Wikipedia summary data
    """
    return get_summary(topic)


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
    return {
        "query": query,
        "subreddit": subreddit,
        "count": len(results),
        "results": results,
    }


def get_weather() -> dict:
    """
    Get current weather for South Florida.

    Returns:
        Dict with current weather data
    """
    return get_current_weather()
