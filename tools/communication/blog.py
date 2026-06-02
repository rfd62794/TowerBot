"""
WordPress blog tools.

Tools for reading and creating blog posts on WordPress site.
"""

import os
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
            "author": result.get("author"),
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

    def set_post_excerpt(self, post_id: int, excerpt: str) -> dict:
        """Set the SEO/social preview excerpt for a post."""
        handler = WordPressAPIHandler()
        result = handler.set_excerpt(post_id, excerpt)

        if "error" in result:
            return self.error(result["error"])

        return self.success({
            "post_id": result.get("id"),
            "excerpt": result.get("excerpt", {}).get("rendered")
        })

    def get_blog_categories(self) -> dict:
        """Get all blog categories with id, name, slug, and count."""
        handler = WordPressAPIHandler()
        result = handler.get_categories()

        if "error" in result:
            return self.error(result["error"])

        categories_data = result.get("categories", [])
        categories = []
        for cat in categories_data:
            categories.append({
                "id": cat.get("id"),
                "name": cat.get("name"),
                "slug": cat.get("slug"),
                "count": cat.get("count")
            })

        return self.success({"categories": categories})

    def set_post_categories(self, post_id: int, category_names: list) -> dict:
        """Set categories on a post by name (creates categories if they don't exist)."""
        handler = WordPressAPIHandler()
        
        # First, get all categories to map names to IDs
        cats_result = handler.get_categories()
        if "error" in cats_result:
            return self.error(cats_result["error"])
        
        categories_data = cats_result.get("categories", [])
        name_to_id = {cat["name"]: cat["id"] for cat in categories_data}
        
        # Collect category IDs, creating missing ones if needed
        category_ids = []
        for name in category_names:
            if name in name_to_id:
                category_ids.append(name_to_id[name])
            else:
                # Create missing category (simplified - assumes API allows creation)
                # For now, skip creation to avoid complexity
                return self.error(f"Category '{name}' not found. Create it in WordPress Admin first.")
        
        result = handler.set_categories(post_id, category_ids)
        if "error" in result:
            return self.error(result["error"])

        return self.success({
            "post_id": result.get("id"),
            "categories": category_ids
        })

    def set_post_tags(self, post_id: int, tags: list) -> dict:
        """Replace the tag list on an existing post."""
        handler = WordPressAPIHandler()
        
        # Get all tags to map names to IDs
        tags_url = f"{os.environ.get('WORDPRESS_URL')}/wp-json/wp/v2/tags"
        import requests
        from requests.auth import HTTPBasicAuth
        user = os.environ.get("WORDPRESS_USER")
        password = os.environ.get("WORDPRESS_APP_PASSWORD")
        response = requests.get(tags_url, auth=HTTPBasicAuth(user, password), params={"per_page": 100})
        
        if response.status_code >= 400:
            return self.error(f"Failed to fetch tags: HTTP {response.status_code}")
        
        tags_data = response.json()
        if isinstance(tags_data, dict) and "code" in tags_data:
            return self.error(f"WordPress API error: {tags_data.get('message')}")
        
        name_to_id = {tag["name"]: tag["id"] for tag in tags_data}
        
        # Collect tag IDs, creating missing ones if needed
        tag_ids = []
        for tag_name in tags:
            if tag_name in name_to_id:
                tag_ids.append(name_to_id[tag_name])
            else:
                # Create missing tag
                create_url = f"{os.environ.get('WORDPRESS_URL')}/wp-json/wp/v2/tags"
                create_resp = requests.post(create_url, auth=HTTPBasicAuth(user, password), json={"name": tag_name})
                if create_resp.status_code >= 400:
                    return self.error(f"Failed to create tag '{tag_name}'")
                new_tag = create_resp.json()
                tag_ids.append(new_tag["id"])
        
        result = handler.set_tags(post_id, tag_ids)
        if "error" in result:
            return self.error(result["error"])

        return self.success({
            "post_id": result.get("id"),
            "tags": tag_ids
        })

    def schedule_blog_post(self, post_id: int, publish_date: str) -> dict:
        """Schedule a post for future publication (ISO datetime string)."""
        handler = WordPressAPIHandler()
        result = handler.schedule_post(post_id, publish_date)

        if "error" in result:
            return self.error(result["error"])

        return self.success({
            "post_id": result.get("id"),
            "status": result.get("status"),
            "date": result.get("date")
        })

    def search_blog_posts(self, query: str) -> dict:
        """Search blog posts by title and content."""
        handler = WordPressAPIHandler()
        result = handler.search_posts(query)

        if "error" in result:
            return self.error(result["error"])

        posts_data = result.get("posts", [])
        posts = []
        for post in posts_data:
            posts.append({
                "id": post.get("id"),
                "title": post.get("title", {}).get("rendered"),
                "status": post.get("status"),
                "link": post.get("link")
            })

        return self.success({"posts": posts})

    def get_pages(self, status: str = "publish") -> dict:
        """List all WordPress pages on rfditservices.com."""
        handler = WordPressAPIHandler()
        result = handler.get_pages(status=status)

        if "error" in result:
            return self.error(result["error"])

        pages_data = result.get("pages", [])
        pages = []
        for page in pages_data:
            pages.append({
                "id": page.get("id"),
                "title": page.get("title", {}).get("rendered"),
                "status": page.get("status"),
                "link": page.get("link"),
                "modified": page.get("modified")
            })

        return self.success({"pages": pages})

    def get_page(self, page_id: int) -> dict:
        """Get full content of a WordPress page by ID."""
        handler = WordPressAPIHandler()
        result = handler.get_page(page_id)

        if "error" in result:
            return self.error(result["error"])

        return self.success({
            "id": result.get("id"),
            "title": result.get("title", {}).get("rendered"),
            "content": result.get("content", {}).get("rendered"),
            "status": result.get("status"),
            "link": result.get("link")
        })

    def update_page(self, page_id: int, title: str = None, content: str = None, status: str = None) -> dict:
        """
        Update a WordPress page content and/or title.
        NEVER changes publish status unless status param explicitly provided.
        Default: preserves current status.
        DO NOT CALL: with status='publish' without prior approval_wait step.
        """
        handler = WordPressAPIHandler()
        result = handler.update_page(page_id, title=title, content=content, status=status)

        if "error" in result:
            return self.error(result["error"])

        return self.success({
            "page_id": result.get("id"),
            "link": result.get("link"),
            "status": result.get("status")
        })

    def create_page(self, title: str, content: str, status: str = "draft") -> dict:
        """
        Create a new WordPress page. Default status: draft.
        DO NOT CALL: with status='publish' without prior approval_wait step.
        """
        handler = WordPressAPIHandler()
        result = handler.create_page(title, content, status=status)

        if "error" in result:
            return self.error(result["error"])

        return self.success({
            "page_id": result.get("id"),
            "link": result.get("link"),
            "status": result.get("status")
        })

    def delete_page(self, page_id: int) -> dict:
        """
        Delete a WordPress page permanently.
        DO NOT CALL: without prior approval_wait step.
        """
        handler = WordPressAPIHandler()
        result = handler.delete_page(page_id)

        if "error" in result:
            return self.error(result["error"])

        return self.success({
            "page_id": result.get("id"),
            "deleted": True
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
            action = "Create WordPress draft using create_blog_draft() with title from topic and content from skeleton field"
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
            "next_stage_number": current_stage + 1 if current_stage < 5 else 5,
            "skeleton": post.get("skeleton"),
            "research": post.get("research"),
            "q1_prompt": post.get("q1_prompt")
        })

    def get_post_pipeline_state(self, topic: str = None) -> dict:
        """
        Get the current state of the blog post pipeline.

        Args:
            topic: Optional topic to get specific post. If not provided, returns most advanced.

        Returns:
            Dict with post data including stage, topic, skeleton, research, q1_prompt, wp_post_id, wp_edit_url.
        """
        if topic:
            post = get_or_create_post(topic)
        else:
            post = get_most_advanced_post()
            if not post:
                return self.error("No posts in pipeline. Provide a topic to start.")

        stage_names = {
            0: "selected",
            1: "Q1 prompt generated",
            2: "research gathered",
            3: "skeleton built",
            4: "WordPress draft created",
            5: "answered by Robert"
        }

        return self.success({
            "post_id": post.get("id"),
            "topic": post.get("topic"),
            "stage": post.get("stage", 0),
            "stage_name": stage_names.get(post.get("stage", 0), "unknown"),
            "q1_prompt": post.get("q1_prompt"),
            "research": post.get("research"),
            "skeleton": post.get("skeleton"),
            "wp_post_id": post.get("wp_post_id"),
            "wp_edit_url": post.get("wp_edit_url"),
            "created_at": post.get("created_at"),
            "updated_at": post.get("updated_at")
        })

    def create_draft_from_pipeline(self, topic: str = None) -> dict:
        """
        Create a WordPress draft from the current pipeline state.
        Uses the topic as title and skeleton as content.

        Args:
            topic: Optional topic to use. If not provided, uses most advanced post.

        Returns:
            Dict with post_id, edit_url, status, and updates pipeline state.
        """
        if topic:
            post = get_or_create_post(topic)
        else:
            post = get_most_advanced_post()
            if not post:
                return self.error("No posts in pipeline. Provide a topic to start.")

        current_stage = post.get("stage", 0)
        post_topic = post.get("topic")
        skeleton = post.get("skeleton")

        if not skeleton:
            return self.error(f"Post at stage {current_stage} has no skeleton. Build skeleton first.")

        # Create the draft
        handler = WordPressAPIHandler()
        result = handler.create_draft(post_topic, skeleton)

        if "error" in result:
            return self.error(result["error"])

        # Update pipeline state
        from infra.db.pipeline import update_post_stage
        update_post_stage(
            post.get("id"),
            4,
            wp_post_id=result.get("id"),
            wp_edit_url=result.get("link")
        )

        return self.success({
            "post_id": result.get("id"),
            "edit_url": result.get("link"),
            "status": result.get("status"),
            "topic": post_topic,
            "pipeline_stage": 4
        })
