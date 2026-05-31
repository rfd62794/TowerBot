"""GitHub API client — recent commits via GitHub REST API."""

import os
import httpx
from api._handler import BaseAPIHandler

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


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
        def _live() -> dict:
            if not GITHUB_TOKEN:
                return {"error": "GITHUB_TOKEN not set"}

            try:
                headers = {
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json",
                }

                # If no username provided, get it from the authenticated user
                if not username:
                    user_resp = httpx.get(
                        "https://api.github.com/user",
                        headers=headers,
                        timeout=10
                    )
                    user_resp.raise_for_status()
                    user_data = user_resp.json()
                    username = user_data.get("login")

                if not username:
                    return {"error": "Could not determine username"}

                # If specific repo provided, fetch commits from that repo
                if repo:
                    url = f"https://api.github.com/repos/{username}/{repo}/commits"
                else:
                    # Fetch from all user's repos (limit to 5 most recently updated)
                    repos_resp = httpx.get(
                        f"https://api.github.com/users/{username}/repos?sort=updated&per_page=5",
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
                        commits_url = f"https://api.github.com/repos/{username}/{repo_name}/commits?per_page={limit}"
                        commits_resp = httpx.get(commits_url, headers=headers, timeout=10)
                        commits_resp.raise_for_status()
                        repo_commits = commits_resp.json()
                        for commit in repo_commits:
                            commit["_repo"] = repo_name
                            commits.append(commit)
                        if len(commits) >= limit:
                            break

                    return {"commits": commits[:limit]}

                # Single repo case
                response = httpx.get(
                    f"{url}?per_page={limit}",
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                commits = response.json()

                # Add repo name to each commit
                for commit in commits:
                    commit["_repo"] = repo

                return {"commits": commits}

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    return {"error": "Invalid GitHub token"}
                if e.response.status_code == 404:
                    return {"error": f"Repository {username}/{repo} not found"}
                return {"error": f"HTTP {e.response.status_code}: {e}"}
            except Exception as e:
                return {"error": str(e)}

        result = self.call("commits", self.hash(username, repo, limit), _live, stale_ok=True)

        # Add stale_notice to result
        from infra.cache import cache
        notice = cache.stale_notice(result)
        result["stale_notice"] = notice

        return result


# Module-level instance
github_api = GitHubAPIHandler()

# Module-level function for backwards compat
def get_recent_commits(username: str = None, repo: str = None, limit: int = 10) -> dict:
    return github_api.get_recent_commits(username, repo, limit)
