"""GitHub API client — recent commits via GitHub REST API."""

import os
import httpx
from api._handler import BaseAPIHandler
from infra.cache import cache


class GitHubAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "github"

    def _get_client(self):
        # GitHub uses token in Authorization header
        return None  # Custom auth in requests

    def get_recent_commits(self, username: str = None, repo: str = None, limit: int = 10) -> dict:
        """
        Get recent commits for a user's repositories.

        Args:
            username: GitHub username (default: inferred from token)
            repo: Specific repository name (optional, e.g. "PrivyBot")
            limit: Number of commits to return (default: 10)

        Returns:
            Dict with commits array containing commit metadata
        """
        def _live(username_param=username, repo_param=repo, limit_param=limit) -> dict:
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                return {"error": "GITHUB_TOKEN not set"}

            try:
                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                }

                # If no username provided, get it from the authenticated user
                resolved_username = username_param if username_param else None
                if not resolved_username:
                    user_resp = httpx.get(
                        "https://api.github.com/user",
                        headers=headers,
                        timeout=10
                    )
                    user_resp.raise_for_status()
                    user_data = user_resp.json()
                    resolved_username = user_data.get("login")

                if not resolved_username:
                    return {"error": "Could not determine username"}

                # If specific repo provided, fetch commits from that repo
                if repo_param:
                    url = f"https://api.github.com/repos/{resolved_username}/{repo_param}/commits"
                else:
                    # Fetch from all user's repos (limit to 5 most recently updated)
                    repos_resp = httpx.get(
                        f"https://api.github.com/users/{resolved_username}/repos?sort=updated&per_page=5",
                        headers=headers,
                        timeout=10
                    )
                    repos_resp.raise_for_status()
                    repos = repos_resp.json()

                    # Get commits from each repo
                    commits = []
                    for repo_data in repos[:3]:  # Top 3 repos
                        repo_name = repo_data.get("name")
                        if not repo_name:
                            continue
                        commits_url = f"https://api.github.com/repos/{resolved_username}/{repo_name}/commits?per_page={limit_param}"
                        commits_resp = httpx.get(commits_url, headers=headers, timeout=10)
                        commits_resp.raise_for_status()
                        repo_commits = commits_resp.json()
                        for commit in repo_commits:
                            commit["_repo"] = repo_name
                            commits.append(commit)
                        if len(commits) >= limit_param:
                            break

                    return {"commits": commits[:limit_param]}

                # Single repo case
                response = httpx.get(
                    f"{url}?per_page={limit_param}",
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                commits = response.json()

                # Add repo name to each commit
                for commit in commits:
                    commit["_repo"] = repo_param

                return {"commits": commits}

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    return {"error": "Invalid GitHub token"}
                if e.response.status_code == 404:
                    user_display = resolved_username or 'unknown'
                    return {"error": f"Repository {user_display}/{repo_param} not found" if repo_param else f"User {user_display} not found"}
                return {"error": f"HTTP {e.response.status_code}: {e}"}
            except Exception as e:
                return {"error": str(e)}

        # Capture parameters before call to avoid scoping issues
        _call_username = username
        _call_repo = repo
        _call_limit = limit
        result = self.call("commits", self.hash(_call_username, _call_repo, _call_limit), _live, stale_ok=True)

        # Add stale_notice to result
        notice = cache.stale_notice(result)
        result["stale_notice"] = notice

        return result


# Module-level instance
github_api = GitHubAPIHandler()

# Module-level function for backwards compat
def get_recent_commits(username: str = None, repo: str = None, limit: int = 10) -> dict:
    return github_api.get_recent_commits(username, repo, limit)
