"""
WordPress blog tools.

Tools for reading and creating blog posts on WordPress site.
"""

from api._handler import BaseTool
from api.web.wordpress_api import WordPressAPIHandler
from infra.db.pipeline import get_most_advanced_post, get_or_create_post, update_post_stage


class BlogTools(BaseTool):
    def get_blog_posts(self, status: str = "draft") -> dict:
        """List blog posts with id, title, status, modified date."""
        handler = WordPressAPIHandler()
        result = handler.get_posts(status=status)

        if "error" in result:
            return self.error(result["error"])

        # Extract posts from wrapper dict
        posts_data = result.get("posts", [])

        posts = []
        for post in posts_data:
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

    def update_blog_post(self, post_id: int, title: str = None, content: str = None, status: str = None) -> dict:
        """Update blog post title, content, or status."""
        handler = WordPressAPIHandler()
        result = handler.update_post(post_id, title, content, status)

        if "error" in result:
            return self.error(result["error"])

        return self.success({
            "post_id": result.get("id"),
            "status": result.get("status"),
            "link": result.get("link")
        })

    def advance_post_pipeline(self, topic: str = None) -> dict:
        """
        Advance the most in-progress blog post by exactly one stage.

        Stages: 0=selected, 1=Q1, 2=research, 3=skeleton, 4=draft, 5=answered

        Args:
            topic: Optional topic to start new post. If not provided, uses most advanced in-progress.

        Returns:
            Dict with current stage, topic, action taken, and next stage description.
        """
        # Get or create post
        if topic:
            post = get_or_create_post(topic)
        else:
            post = get_most_advanced_post()
            if not post:
                return self.error("No posts in progress. Provide a topic to start.")

        current_stage = post.get("stage", 0)
        post_id = post.get("id")
        post_topic = post.get("topic")

        # Stage descriptions
        stage_names = {
            0: "selected",
            1: "Q1 prompt generated",
            2: "research gathered",
            3: "skeleton built",
            4: "WordPress draft created",
            5: "answered by Robert"
        }

        # Action based on current stage
        if current_stage == 0:
            action = "Generate Q1 prompt for the topic"
            next_stage = "Generate Q1 prompt and save to q1_prompt field"
        elif current_stage == 1:
            action = "Gather research using available tools"
            next_stage = "Gather research and save to research field"
        elif current_stage == 2:
            action = "Build 5-section skeleton (MOMENT, SURPRISE, STRUGGLE, LESSON, NEXT)"
            next_stage = "Build skeleton with prompts and research context"
        elif current_stage == 3:
            action = "Create WordPress draft using create_blog_draft()"
            next_stage = "Create draft and save wp_post_id and wp_edit_url"
        elif current_stage == 4:
            action = "Waiting for Robert to answer the 5 questions"
            next_stage = "Robert answers questions in WordPress editor"
        else:
            return self.error(f"Post already at final stage (stage {current_stage})")

        return self.success({
            "stage": current_stage,
            "stage_name": stage_names.get(current_stage, "unknown"),
            "topic": post_topic,
            "post_id": post_id,
            "action_taken": action,
            "next_stage": next_stage,
            "next_stage_number": current_stage + 1 if current_stage < 5 else 5
        })
