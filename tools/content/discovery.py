"""Discovery and traffic tools."""

import hashlib
import json
from datetime import datetime, timedelta
from tools._tool import BaseTool
from tools.api.youtube_api import query_traffic_sources


class DiscoveryTools(BaseTool):
    """YouTube discovery tools with BaseTool pattern."""

    def get_traffic_sources(self, days: int = 28) -> dict:
        """
        Get top search terms that find your videos.

        Args:
            days: Number of days to look back (default: 28)

        Returns:
            Dict with top search terms and view counts
        """
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            api_response = query_traffic_sources(start, end)
            if "error" in api_response:
                return self.error(api_response["error"], code="api_failed")

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

            return self.success(result, stale_result=api_response)
        except Exception as e:
            return self.error(str(e), code="exception")


# Module-level instance
_discovery_tools = DiscoveryTools()


# Backwards compat module-level function
def get_traffic_sources(days: int = 28) -> dict:
    return _discovery_tools.get_traffic_sources(days)
