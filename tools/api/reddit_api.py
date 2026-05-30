"""Reddit API client — raw API calls only."""

import requests

HEADERS = {
    "User-Agent": "PrivyBot/1.0 (personal tool)"
}


def search_reddit(query: str, subreddit: str = None, sort: str = "relevance", limit: int = 10) -> list[dict]:
    """
    Search Reddit posts.

    Args:
        query: Search query
        subreddit: Optional subreddit to search within
        sort: Sort order (relevance, new, hot, top)
        limit: Maximum results to return

    Returns:
        List of dicts with post data
    """
    try:
        if subreddit:
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
        else:
            url = "https://www.reddit.com/search.json"
        
        params = {
            "q": query,
            "sort": sort,
            "limit": limit,
            "restrict_sr": bool(subreddit)
        }
        
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
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
        
        return posts
    except Exception:
        return []
