"""DuckDuckGo search API client — raw API calls only."""

from duckduckgo_search import DDGS


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    Search DuckDuckGo for web results.

    Args:
        query: Search query
        max_results: Maximum results to return

    Returns:
        List of dicts with title, url, body
    """
    try:
        results = []
        ddgs = DDGS()
        for result in ddgs.text(query, max_results=max_results):
            results.append({
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "body": result.get("body", ""),
            })
        return results
    except Exception:
        return []


def search_news(query: str, max_results: int = 5) -> list[dict]:
    """
    Search DuckDuckGo for news results.

    Args:
        query: Search query
        max_results: Maximum results to return

    Returns:
        List of dicts with title, url, body, date, source
    """
    try:
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
        return results
    except Exception:
        return []
