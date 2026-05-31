"""
WordPress REST API handler.

Connects to WordPress site to read and create blog posts.
Uses Application Passwords for authentication.
"""

import os
import requests
from requests.auth import HTTPBasicAuth

from api._handler import BaseAPIHandler
from infra.cache import cache


class WordPressAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "wordpress"

    def _get_client(self):
        """Return HTTPBasicAuth client with WordPress credentials."""
        user = os.environ.get("WORDPRESS_USER")
        password = os.environ.get("WORDPRESS_APP_PASSWORD")
        return HTTPBasicAuth(user, password)

    def get_posts(self, status: str = "draft") -> dict:
        """GET /wp-json/wp/v2/posts"""
        def _live():
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/posts"
            params = {"status": status, "per_page": 100}
            response = requests.get(url, auth=self._get_client(), params=params)
            return response.json()
        return self.call("posts", self.hash(status), _live)

    def get_post(self, post_id: int) -> dict:
        """GET /wp-json/wp/v2/posts/{id}"""
        def _live():
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/posts/{post_id}"
            response = requests.get(url, auth=self._get_client())
            return response.json()
        return self.call(f"post_{post_id}", self.hash(post_id), _live)

    def create_draft(self, title: str, content: str, tags: list = None) -> dict:
        """POST /wp-json/wp/v2/posts with status=draft"""
        # Write operation — bypass self.call() entirely
        try:
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/posts"
            data = {
                "title": title,
                "content": content,
                "status": "draft",
                "tags": tags or []
            }
            response = requests.post(url, auth=self._get_client(), json=data)
            result = response.json()
            # Invalidate posts cache so next read is fresh
            cache.invalidate(self.cache_key("posts"))
            return result
        except Exception as e:
            return {"error": str(e), "_live_failed": True}

    def update_post(self, post_id: int, content: str = None, status: str = None) -> dict:
        """PUT /wp-json/wp/v2/posts/{id}"""
        # Write operation — bypass self.call() entirely
        try:
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/posts/{post_id}"
            data = {}
            if content:
                data["content"] = content
            if status:
                data["status"] = status
            response = requests.put(url, auth=self._get_client(), json=data)
            result = response.json()
            # Invalidate post cache so next read is fresh
            cache.invalidate(self.cache_key(f"post_{post_id}"))
            return result
        except Exception as e:
            return {"error": str(e), "_live_failed": True}
