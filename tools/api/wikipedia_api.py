"""Wikipedia API client — raw API calls only."""

import requests


WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1"


def get_summary(topic: str) -> dict:
    """
    Get Wikipedia article summary for a topic.

    Args:
        topic: Topic to look up (article title)

    Returns:
        Dict with title, description, extract, found status
    """
    try:
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
    except Exception as e:
        return {
            "found": False,
            "error": str(e),
        }
