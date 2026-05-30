"""Fetch API client — browser tool for reading web pages."""

import re
import requests
from tools.api._handler import BaseAPIHandler


class FetchAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "fetch"

    HEADERS = {
        "User-Agent": "PrivyBot/1.0 (personal tool)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def _get_client(self):
        return None  # requests needs no client

    def fetch_url(self, url: str, max_chars: int = 3000) -> dict:
        """
        Fetch and read the full text content of a web page.

        Args:
            url: The full URL to fetch including https:// prefix
            max_chars: Maximum characters to return (default 3000)

        Returns:
            Dict with url, title, content, char_count, truncated, status_code
        """
        params_hash = self.hash(url, max_chars)

        def _live() -> dict:
            from bs4 import BeautifulSoup

            response = requests.get(
                url,
                headers=self.HEADERS,
                timeout=10,
                allow_redirects=True
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove noise elements
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
                tag.decompose()

            # Extract title
            title = ""
            if soup.title and soup.title.string:
                title = soup.title.string.strip()

            # Extract text
            text = soup.get_text(separator=" ", strip=True)
            text = re.sub(r'\s+', ' ', text).strip()

            return {
                "url": url,
                "title": title,
                "content": text[:max_chars],
                "char_count": len(text),
                "truncated": len(text) > max_chars,
                "status_code": response.status_code
            }

        return self.call("page", params_hash, _live, stale_ok=True)


# Module-level instance
fetch_api = FetchAPIHandler()


# Backwards compat function
def fetch_url(url: str, max_chars: int = 3000) -> dict:
    return fetch_api.fetch_url(url, max_chars)
