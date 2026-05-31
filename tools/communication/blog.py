"""
WordPress blog tools.

Tools for reading and creating blog posts on WordPress site.
"""

from api._handler import BaseTool
from api.web.wordpress_api import WordPressAPIHandler


class BlogTools(BaseTool):
    def get_blog_posts(self, status: str = "draft") -> dict:
        """List blog posts with id, title, status, modified date."""
        handler = WordPressAPIHandler()
        result = handler.get_posts(status=status)

        if "error" in result:
            return self.error(result["error"])

        # cache.call() wraps non-dict results in {"value": result}
        posts_list = result.get("value", result) if isinstance(result, dict) and "value" in result else result

        # Handle case where result is already a list (no cache hit)
        if not isinstance(posts_list, list):
            return self.error(f"Expected list of posts, got {type(posts_list)}")

        posts = []
        for post in posts_list:
            posts.append({
                "id": post.get("id"),
                "title": post.get("title", {}).get("rendered"),
                "status": post.get("status"),
                "modified": post.get("modified"),
                "link": post.get("link")
            })

        return self.success({"posts": posts})

    def get_blog_post(self, post_id: int) -> dict:
        """Get full content of one post."""
        handler = WordPressAPIHandler()
        result = handler.get_post(post_id)

        if "error" in result:
            return self.error(result["error"])

        return self.success({
            "id": result.get("id"),
            "title": result.get("title", {}).get("rendered"),
            "content": result.get("content", {}).get("rendered"),
            "status": result.get("status"),
            "link": result.get("link")
        })

    def create_blog_draft(self, title: str, content: str, tags: list = None) -> dict:
        """Create a new blog draft."""
        handler = WordPressAPIHandler()
        result = handler.create_draft(title, content, tags)

        if "error" in result:
            return self.error(result["error"])

        return self.success({
            "post_id": result.get("id"),
            "edit_url": result.get("link"),
            "status": result.get("status")
        })

    def update_blog_post(self, post_id: int, content: str = None, status: str = None) -> dict:
        """Update blog post content or status."""
        handler = WordPressAPIHandler()
        result = handler.update_post(post_id, content, status)

        if "error" in result:
            return self.error(result["error"])

        return self.success({
            "post_id": result.get("id"),
            "status": result.get("status"),
            "link": result.get("link")
        })
