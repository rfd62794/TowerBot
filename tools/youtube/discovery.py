"""Discovery and traffic tools."""

import hashlib
import json
from datetime import datetime, timedelta
from core.db import cache_tool_result, get_cached_tool_result
from tools.api.youtube_api import query_traffic_sources


def _hash_params(params: dict) -> str:
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()


def get_traffic_sources(days: int = 28) -> dict:
    """
    Get top search terms that find your videos.

    Args:
        days: Number of days to look back (default: 28)

    Returns:
        Dict with top search terms and view counts
    """
    params = {"days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_traffic_sources", params_hash)
    if cached:
        return cached

    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_traffic_sources(start, end)
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [])
        top_terms = []
        for row in rows:
            top_terms.append({
                "term": row[0],
                "views": int(row[1])
            })

        result = {
            "top_search_terms": top_terms,
            "period_days": days,
        }

        cache_tool_result("get_traffic_sources", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}
