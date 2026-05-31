# WordPress Blog Tools

## Purpose

Connect PrivyBot to rfditservices.com WordPress site to create blog drafts directly instead of saving to memory. This changes the blog pipeline from memory tracking to actual content creation.

## Architecture

### WordPress REST API

WordPress has a built-in REST API — no plugin needed. Uses Application Passwords for authentication.

**Setup:**
1. Go to WordPress Admin → Settings → Users
2. Generate Application Password (2 minutes)
3. Add to .env:
```bash
WORDPRESS_URL=https://rfditservices.com
WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

### API Handler

**File:** `api/web/wordpress_api.py`

```python
class WordPressAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "wordpress"
    
    def _get_client(self):
        from requests.auth import HTTPBasicAuth
        import os
        user = os.environ.get("WORDPRESS_USER")
        password = os.environ.get("WORDPRESS_APP_PASSWORD")
        return HTTPBasicAuth(user, password)
    
    def get_posts(self, status="draft") -> dict:
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
```

### Tool Layer

**File:** `tools/communication/blog.py`

```python
class BlogTools(BaseTool):
    def get_blog_posts(self, status: str = "draft") -> dict:
        """List blog posts with id, title, status, modified date."""
        handler = WordPressAPIHandler()
        result = handler.get_posts(status=status)
        
        if "error" in result:
            return self.error(result["error"])
        
        posts = []
        for post in result:
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
```

## Updated Blog Pipeline

### Before (Memory-Only)

```
blog_structure_generator runs Sunday 1AM
→ generates skeleton using RFD Content Frame
→ saves to memory 'Blog draft YYYY-MM-DD: [topic]'
→ Robert wakes up Monday, reads memory, manually creates WordPress post
```

### After (WordPress Integration)

```
blog_structure_generator runs Sunday 1AM
→ generates skeleton using RFD Content Frame
→ calls create_blog_draft() instead of save_memory()
→ Robert wakes up Monday with a WordPress draft waiting
→ adds authentic voice in WordPress editor
→ publishes
```

### Morning Briefing Addition

```
📝 Blog draft waiting for review
   - "How I Write Directives That Coding Agents Actually Follow"
   - Edit: https://rfditservices.com/wp-admin/post.php?post=123
```

## Tool Registry

Add to `tools/registry.py`:

```python
from .communication.blog import BlogTools

blog_tools = BlogTools()

TOOL_REGISTRY = {
    "get_blog_posts": {
        "fn": blog_tools.get_blog_posts,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_blog_posts",
                "description": "List blog posts from WordPress with id, title, status, and modified date.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Filter by status: draft, publish, or all",
                            "default": "draft"
                        }
                    },
                    "required": []
                }
            }
        }
    },
    "get_blog_post": {
        "fn": blog_tools.get_blog_post,
        "definition": {
            "type": "function",
            "function": {
                "name": "get_blog_post",
                "description": "Get full content of a specific blog post by ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "integer",
                            "description": "WordPress post ID"
                        }
                    },
                    "required": ["post_id"]
                }
            }
        }
    },
    "create_blog_draft": {
        "fn": blog_tools.create_blog_draft,
        "definition": {
            "type": "function",
            "function": {
                "name": "create_blog_draft",
                "description": "Create a new blog draft in WordPress. Returns post ID and edit URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Post title"
                        },
                        "content": {
                            "type": "string",
                            "description": "Post content (HTML or plain text)"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of tags"
                        }
                    },
                    "required": ["title", "content"]
                }
            }
        }
    },
    "update_blog_post": {
        "fn": blog_tools.update_blog_post,
        "definition": {
            "type": "function",
            "function": {
                "name": "update_blog_post",
                "description": "Update blog post content or promote draft to scheduled/publish.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "integer",
                            "description": "WordPress post ID"
                        },
                        "content": {
                            "type": "string",
                            "description": "Updated content (optional)"
                        },
                        "status": {
                            "type": "string",
                            "description": "New status: draft, publish, scheduled (optional)"
                        }
                    },
                    "required": ["post_id"]
                }
            }
        }
    },
}
```

## Updated blog_structure_generator Prompt

```python
"blog_structure_generator": {
    "schedule_type": "cron",
    "hour": 1,
    "minute": 0,
    "day_of_week": 6,
    "enabled": True,
    "prompt": (
        "Check memory for 'Blog humanization status' — are all 4 existing posts humanized? "
        "If not: identify which post is next, call get_blog_post() to pull current content, "
        "apply five-question extraction frame, draft opening rewrite. "
        "Call update_blog_post() to save the rewrite. "
        "Save as memory 'Blog rewrite ready: [post name]'. "
        "If all 4 are humanized: check recent commits and YouTube performance, "
        "pick the highest-resonance topic from the 70-post inventory, "
        "generate five-question extraction skeleton using RFD Content Frame "
        "(MOMENT → SURPRISE → STRUGGLE → LESSON → NEXT). "
        "Call create_blog_draft() to create WordPress draft. "
        "Save as memory 'Blog draft created: [topic]'. "
        "Mark URGENT."
    ),
},
```

## Environment Variables

Add to `.env`:
```bash
WORDPRESS_URL=https://rfditservices.com
WORDPRESS_USER=robert  # WordPress username
WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx  # Generated in WordPress Admin
```

## Cache TTL Configuration

Add to `infra/cache.py` TTL dict:

```python
TTL = {
    # ... existing entries ...
    "wordpress_posts": 300,    # 5min — drafts change frequently
    "wordpress_post": 300,     # 5min — individual post
}
```

## Stop Rule

**Files to modify:**
- `api/web/wordpress_api.py` — NEW
- `tools/communication/blog.py` — NEW
- `tools/registry.py` — add 4 tool entries
- `infra/cache.py` — add TTL entries
- `bot/autonomous.py` — update blog_structure_generator prompt
- `.env` — add WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_APP_PASSWORD

**Explicitly NOT in scope:**
- Morning briefing "📝 Blog draft waiting" section — defer to follow-up directive

## Testing

Tests will need to mock `requests.get/post/put` since WordPress API cannot be hit in CI.

```python
# tests/test_wordpress_api.py
import unittest.mock as mock

@mock.patch('requests.get')
def test_get_posts(mock_get):
    mock_get.return_value.json.return_value = [{"id": 1, "title": {"rendered": "Test"}}]
    handler = WordPressAPIHandler()
    result = handler.get_posts(status="draft")
    assert result[0]["id"] == 1

@mock.patch('requests.post')
def test_create_draft(mock_post):
    mock_post.return_value.json.return_value = {"id": 123, "link": "https://..."}
    handler = WordPressAPIHandler()
    result = handler.create_draft("Test", "Content")
    assert result["id"] == 123
```

- Generate Application Password: 2 minutes
- Build wordpress_api.py: 30 minutes
- Build blog.py tools: 30 minutes
- Add to registry + tests: 30 minutes
- **Total: ~90 minutes**

## Priority

**High** — Changes where blog output lands. Important before generating more drafts.
