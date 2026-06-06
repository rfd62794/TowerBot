"""Jina Reader API client — raw API calls only."""

import requests


class JinaReaderAPI:
    BASE = "https://r.jina.ai"

    def read_url(self, url: str, timeout: int = 30) -> dict:
        """
        Read a web page using Jina Reader API.

        Args:
            url: The full URL to fetch including https:// prefix
            timeout: Request timeout in seconds (default 30)

        Returns:
            Dict with url, content
        """
        try:
            resp = requests.get(f"{self.BASE}/{url}", timeout=timeout)
            resp.raise_for_status()
            return {"ok": True, "url": url, "content": resp.text[:8000]}
        except Exception as e:
            return {"ok": False, "error": str(e), "url": url}


# Module-level instance
jina_reader_api = JinaReaderAPI()


# Backwards compat
def read_url(url: str, timeout: int = 30) -> dict:
    result = jina_reader_api.read_url(url, timeout)
    return result
