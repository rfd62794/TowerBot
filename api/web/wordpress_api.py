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
            posts = response.json()  # WordPress returns a list
            # WordPress API returns list on success, dict on error
            if isinstance(posts, dict) and "code" in posts:
                raise Exception(f"WordPress API error: {posts.get('message', 'Unknown error')}")
            return {"posts": posts}  # Wrap for BaseAPIHandler
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
            # Explicitly set author if WORDPRESS_AUTHOR_ID is present
            author_id = os.environ.get("WORDPRESS_AUTHOR_ID")
            if author_id:
                data["author"] = int(author_id)
            response = requests.post(url, auth=self._get_client(), json=data)
            result = response.json()
            # Invalidate posts cache so next read is fresh
            cache.invalidate(self.cache_key("posts"))
            return result
        except Exception as e:
            return {"error": str(e), "_live_failed": True}

    def update_post(self, post_id: int, title: str = None, content: str = None, status: str = None) -> dict:
        """PUT /wp-json/wp/v2/posts/{id}"""
        # Write operation — bypass self.call() entirely
        try:
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/posts/{post_id}"
            data = {}
            if title:
                data["title"] = title
            if content:
                data["content"] = content
            if status:
                data["status"] = status
            
            response = requests.put(url, auth=self._get_client(), json=data)
            
            # Log response for debugging
            print(f"[WordPress API] PUT response status: {response.status_code}")
            print(f"[WordPress API] PUT response body: {response.text[:500]}")
            
            # Check for error response
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    return {"error": error_data.get("message", f"HTTP {response.status_code}"), "_live_failed": True}
                except:
                    return {"error": f"HTTP {response.status_code}", "_live_failed": True}
            
            result = response.json()
            
            # Validate that we got a proper post object back
            if not isinstance(result, dict) or "id" not in result:
                return {"error": f"Invalid response from WordPress: {result}", "_live_failed": True}
            
            # Invalidate post cache so next read is fresh
            cache.invalidate(self.cache_key(f"post_{post_id}"))
            return result
        except Exception as e:
            return {"error": str(e), "_live_failed": True}

    def get_categories(self) -> dict:
        """GET /wp-json/wp/v2/categories"""
        def _live():
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/categories"
            params = {"per_page": 100}
            response = requests.get(url, auth=self._get_client(), params=params)
            categories = response.json()
            if isinstance(categories, dict) and "code" in categories:
                raise Exception(f"WordPress API error: {categories.get('message', 'Unknown error')}")
            return {"categories": categories}
        return self.call("categories", self.hash("all"), _live)

    def set_excerpt(self, post_id: int, excerpt: str) -> dict:
        """PUT /wp-json/wp/v2/posts/{id} with excerpt field"""
        try:
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/posts/{post_id}"
            data = {"excerpt": excerpt}
            response = requests.put(url, auth=self._get_client(), json=data)
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    return {"error": error_data.get("message", f"HTTP {response.status_code}"), "_live_failed": True}
                except:
                    return {"error": f"HTTP {response.status_code}", "_live_failed": True}
            
            result = response.json()
            if not isinstance(result, dict) or "id" not in result:
                return {"error": f"Invalid response from WordPress: {result}", "_live_failed": True}
            
            cache.invalidate(self.cache_key(f"post_{post_id}"))
            return result
        except Exception as e:
            return {"error": str(e), "_live_failed": True}

    def set_categories(self, post_id: int, category_ids: list) -> dict:
        """PUT /wp-json/wp/v2/posts/{id} with category IDs"""
        try:
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/posts/{post_id}"
            data = {"categories": category_ids}
            response = requests.put(url, auth=self._get_client(), json=data)
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    return {"error": error_data.get("message", f"HTTP {response.status_code}"), "_live_failed": True}
                except:
                    return {"error": f"HTTP {response.status_code}", "_live_failed": True}
            
            result = response.json()
            if not isinstance(result, dict) or "id" not in result:
                return {"error": f"Invalid response from WordPress: {result}", "_live_failed": True}
            
            cache.invalidate(self.cache_key(f"post_{post_id}"))
            return result
        except Exception as e:
            return {"error": str(e), "_live_failed": True}

    def set_tags(self, post_id: int, tag_ids: list) -> dict:
        """PUT /wp-json/wp/v2/posts/{id} with tag IDs"""
        try:
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/posts/{post_id}"
            data = {"tags": tag_ids}
            response = requests.put(url, auth=self._get_client(), json=data)
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    return {"error": error_data.get("message", f"HTTP {response.status_code}"), "_live_failed": True}
                except:
                    return {"error": f"HTTP {response.status_code}", "_live_failed": True}
            
            result = response.json()
            if not isinstance(result, dict) or "id" not in result:
                return {"error": f"Invalid response from WordPress: {result}", "_live_failed": True}
            
            cache.invalidate(self.cache_key(f"post_{post_id}"))
            return result
        except Exception as e:
            return {"error": str(e), "_live_failed": True}

    def schedule_post(self, post_id: int, publish_date: str) -> dict:
        """PUT /wp-json/wp/v2/posts/{id} with date and status=future"""
        try:
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/posts/{post_id}"
            data = {"date": publish_date, "status": "future"}
            response = requests.put(url, auth=self._get_client(), json=data)
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    return {"error": error_data.get("message", f"HTTP {response.status_code}"), "_live_failed": True}
                except:
                    return {"error": f"HTTP {response.status_code}", "_live_failed": True}
            
            result = response.json()
            if not isinstance(result, dict) or "id" not in result:
                return {"error": f"Invalid response from WordPress: {result}", "_live_failed": True}
            
            cache.invalidate(self.cache_key(f"post_{post_id}"))
            return result
        except Exception as e:
            return {"error": str(e), "_live_failed": True}

    def search_posts(self, query: str) -> dict:
        """GET /wp-json/wp/v2/posts?search={query}"""
        def _live():
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/posts"
            params = {"search": query, "per_page": 100}
            response = requests.get(url, auth=self._get_client(), params=params)
            posts = response.json()
            if isinstance(posts, dict) and "code" in posts:
                raise Exception(f"WordPress API error: {posts.get('message', 'Unknown error')}")
            return {"posts": posts}
        return self.call("search", self.hash(query), _live)

    def get_pages(self, status: str = "publish") -> dict:
        """GET /wp-json/wp/v2/pages"""
        def _live():
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/pages"
            params = {"per_page": 100, "_fields": "id,title,status,link,modified"}
            if status != "any":
                params["status"] = status
            response = requests.get(url, auth=self._get_client(), params=params)
            pages = response.json()
            if isinstance(pages, dict) and "code" in pages:
                raise Exception(f"WordPress API error: {pages.get('message', 'Unknown error')}")
            return {"pages": pages}
        return self.call("pages", self.hash(status), _live)

    def get_page(self, page_id: int) -> dict:
        """GET /wp-json/wp/v2/pages/{id}"""
        def _live():
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/pages/{page_id}"
            response = requests.get(url, auth=self._get_client())
            return response.json()
        return self.call(f"page_{page_id}", self.hash(page_id), _live)

    def update_page(self, page_id: int, title: str = None, content: str = None, status: str = None) -> dict:
        """PUT /wp-json/wp/v2/pages/{id}"""
        # Write operation — bypass self.call() entirely
        try:
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/pages/{page_id}"
            data = {}
            if title:
                data["title"] = title
            if content:
                data["content"] = content
            if status:
                data["status"] = status
            
            if not data:
                return {"error": "Nothing to update — no fields provided", "_live_failed": True}
            
            response = requests.put(url, auth=self._get_client(), json=data)
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    return {"error": error_data.get("message", f"HTTP {response.status_code}"), "_live_failed": True}
                except:
                    return {"error": f"HTTP {response.status_code}", "_live_failed": True}
            
            result = response.json()
            if not isinstance(result, dict) or "id" not in result:
                return {"error": f"Invalid response from WordPress: {result}", "_live_failed": True}
            
            cache.invalidate(self.cache_key(f"page_{page_id}"))
            return result
        except Exception as e:
            return {"error": str(e), "_live_failed": True}

    def create_page(self, title: str, content: str, status: str = "draft") -> dict:
        """POST /wp-json/wp/v2/pages with status=draft by default"""
        # Write operation — bypass self.call() entirely
        try:
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/pages"
            data = {
                "title": title,
                "content": content,
                "status": status
            }
            author_id = os.environ.get("WORDPRESS_AUTHOR_ID")
            if author_id:
                data["author"] = int(author_id)
            response = requests.post(url, auth=self._get_client(), json=data)
            result = response.json()
            cache.invalidate(self.cache_key("pages"))
            return result
        except Exception as e:
            return {"error": str(e), "_live_failed": True}

    def delete_page(self, page_id: int) -> dict:
        """DELETE /wp-json/wp/v2/pages/{id}"""
        # Write operation — bypass self.call() entirely
        try:
            url = f"{os.environ['WORDPRESS_URL']}/wp-json/wp/v2/pages/{page_id}"
            response = requests.delete(url, auth=self._get_client())
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    return {"error": error_data.get("message", f"HTTP {response.status_code}"), "_live_failed": True}
                except:
                    return {"error": f"HTTP {response.status_code}", "_live_failed": True}
            
            result = response.json()
            cache.invalidate(self.cache_key("pages"))
            cache.invalidate(self.cache_key(f"page_{page_id}"))
            return result
        except Exception as e:
            return {"error": str(e), "_live_failed": True}
