"""Search and grounding tools — web, wiki, reddit, weather."""

import hashlib
from datetime import datetime
from api.web.ddg_api import ddg_api
from api.web.wikipedia_api import wikipedia_api
from api.web.reddit_api import reddit_api
from api.weather.weather_api import get_current_weather, weather_api
from api.github.github_api import github_api
from infra.db import record_weather_day
from tools._tool import BaseTool
import httpx


class SearchTools(BaseTool):
    def get_weather(self) -> dict:
        """
        Get current weather for South Florida.

        Returns:
            Dict with current weather data
        """
        raw = get_current_weather()

        if raw.get("_live_failed"):
            return self.error("Weather unavailable", code="api_failed")

        # Record to weather history if fresh
        if not raw.get("_stale"):
            record_weather_day(
                datetime.now().strftime("%Y-%m-%d"),
                raw.get("temp_f", 0),
                raw.get("condition", ""),
                raw.get("wind_mph", 0),
            )

        return self.success(
            {
                "temp_f": raw.get("temp_f"),
                "condition": raw.get("condition"),
                "wind_mph": raw.get("wind_mph"),
                "precipitation_mm": raw.get("precipitation_mm"),
            },
            stale_result=raw,
        )

    def get_weather_forecast(self, days: int = 3) -> dict:
        """
        Get weather forecast for South Florida.

        Args:
            days: Number of forecast days (1-7, default 3)

        Returns:
            Dict with daily forecast data
        """
        from api.weather.weather_api import WMO_CODES

        raw = weather_api.get_forecast(days)

        if raw.get("_live_failed") or "error" in raw:
            return self.error("Weather forecast unavailable", code="api_failed")

        daily = raw.get("daily", {})
        times = daily.get("time", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_probability_max", [])
        codes = daily.get("weathercode", [])

        forecast = []
        for i, date_str in enumerate(times):
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            forecast.append({
                "date": date_str,
                "day_of_week": dt.strftime("%A"),
                "high_f": highs[i] if i < len(highs) else None,
                "low_f": lows[i] if i < len(lows) else None,
                "precipitation_pct": precip[i] if i < len(precip) else None,
                "condition": WMO_CODES.get(
                    int(codes[i]) if i < len(codes) else 0, "Unknown"
                ),
            })

        # Slice to requested number of days
        forecast = forecast[:days]

        return self.success({"days": forecast, "count": len(forecast)},
                            stale_result=raw)

    def get_pypi_stats(self, package: str = "openagent-directive") -> dict:
        """
        Get PyPI download statistics for a package.

        Args:
            package: Package name (default: "openagent-directive")

        Returns:
            Dict with last_day, last_week, last_month, total downloads
        """
        from infra.cache import cache

        cache_key = f"pypi_stats_{package}"
        params_hash = cache.hash(package)

        # Check cache
        cached = cache.get(cache_key, params_hash)
        if cached is not None:
            notice = cache.stale_notice(cached)
            cached["_stale_notice"] = notice
            return cached

        try:
            # Fetch recent downloads
            recent_url = f"https://pypistats.org/api/packages/{package}/recent"
            recent_resp = httpx.get(recent_url, timeout=10)
            recent_resp.raise_for_status()
            recent_data = recent_resp.json()

            # Fetch overall downloads
            overall_url = f"https://pypistats.org/api/packages/{package}/overall"
            overall_resp = httpx.get(overall_url, timeout=10)
            overall_resp.raise_for_status()
            overall_data = overall_resp.json()

            # Extract data
            recent = recent_data.get("data", {})
            overall_list = overall_data.get("data", [])

            # Find without_mirrors total
            total = 0
            for item in overall_list:
                if item.get("category") == "without_mirrors":
                    total = item.get("downloads", 0)
                    break

            result = {
                "ok": True,
                "stale_notice": None,
                "package": package,
                "last_day": recent.get("last_day", 0),
                "last_week": recent.get("last_week", 0),
                "last_month": recent.get("last_month", 0),
                "total": total,
            }

            # Cache for 1 hour using direct cache_tool_result
            from infra.db.cache import cache_tool_result
            cache_tool_result(cache_key, params_hash, result, ttl_hours=1)

            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return self.error(f"Package '{package}' not found on PyPI")
            if e.response.status_code == 429:
                # Rate limited - try stale fallback
                stale = cache.get_or_stale(cache_key, params_hash)
                if stale is not None:
                    notice = cache.stale_notice(stale)
                    stale["_stale_notice"] = notice
                    return stale
                return self.error(f"PyPI API rate limited. Try again later.")
            return self.error(f"PyPI API error: {e}")
        except Exception as e:
            return self.error(f"Failed to fetch PyPI stats: {e}")

    def get_recent_commits(self, username: str = None, repo: str = None, limit: int = 10) -> dict:
        """
        Get recent commits for GitHub repositories.

        Args:
            username: GitHub username (default: inferred from token)
            repo: Specific repository name (optional, e.g. "PrivyBot")
            limit: Number of commits to return (default: 10)

        Returns:
            Dict with commits array containing commit metadata
        """
        raw = github_api.get_recent_commits(username, repo, limit)

        if raw.get("_live_failed") or "error" in raw:
            return self.error("GitHub API unavailable", code="api_failed")

        commits = raw.get("commits", [])

        # Extract key metadata for each commit
        result_commits = []
        for commit in commits:
            commit_data = commit.get("commit", {})
            author = commit_data.get("author", {})
            result_commits.append({
                "sha": commit.get("sha", "")[:7],  # Short SHA
                "message": commit_data.get("message", ""),
                "author": author.get("name", ""),
                "date": author.get("date", ""),
                "repo": commit.get("_repo", ""),
                "url": commit.get("html_url", ""),
            })

        return self.success({
            "count": len(result_commits),
            "commits": result_commits
        }, stale_result=raw)

    def web_search(self, query: str, max_results: int = 5) -> dict:
        """
        Search the web via DuckDuckGo.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            Dict with query, count, and results
        """
        raw = ddg_api.search_web(query, max_results)
        if raw.get("_live_failed"):
            return self.error("Web search unavailable", code="api_failed")
        results = raw.get("results", [])
        return self.success({
            "query": query,
            "count": len(results),
            "results": results
        }, stale_result=raw)

    def news_search(self, query: str, max_results: int = 5) -> dict:
        """
        Search recent news via DuckDuckGo.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            Dict with query, count, and results
        """
        raw = ddg_api.search_news(query, max_results)
        if raw.get("_live_failed"):
            return self.error("News search unavailable", code="api_failed")
        results = raw.get("results", [])
        return self.success({
            "query": query,
            "count": len(results),
            "results": results
        }, stale_result=raw)

    def wiki_lookup(self, topic: str) -> dict:
        """
        Look up a Wikipedia article summary.

        Args:
            topic: Topic to look up

        Returns:
            Dict with Wikipedia summary data
        """
        raw = wikipedia_api.get_summary(topic)
        if raw.get("_live_failed"):
            return self.error("Wikipedia unavailable", code="api_failed")
        # found=False is valid, not an error
        return self.success({
            "found": raw.get("found", False),
            "title": raw.get("title", topic),
            "description": raw.get("description", ""),
            "extract": raw.get("extract", "")
        }, stale_result=raw)

    def reddit_search(self, query: str, subreddit: str = None, limit: int = 10) -> dict:
        """
        Search Reddit posts.

        Args:
            query: Search query
            subreddit: Optional subreddit to search within
            limit: Maximum results to return

        Returns:
            Dict with query, subreddit, count, and results
        """
        raw = reddit_api.search_reddit(query, subreddit, limit=limit)
        if raw.get("_live_failed"):
            return self.error("Reddit search unavailable", code="api_failed")
        results = raw.get("results", [])
        return self.success({
            "query": query,
            "subreddit": subreddit,
            "count": len(results),
            "results": results
        }, stale_result=raw)

    def fetch_url(self, url: str, max_chars: int = 3000) -> dict:
        """
        Fetch and read the full text content of a web page.

        Args:
            url: The full URL to fetch including https:// prefix
            max_chars: Maximum characters to return (default 3000)

        Returns:
            Dict with url, title, content, char_count, truncated
        """
        from api.web.fetch_api import fetch_api

        raw = fetch_api.fetch_url(url, max_chars)

        if raw.get("_live_failed"):
            return self.error(f"Could not fetch: {url}", code="api_failed")

        if "error" in raw:
            return self.error(raw["error"])

        return self.success({
            "url": url,
            "title": raw.get("title", ""),
            "content": raw.get("content", ""),
            "char_count": raw.get("char_count", 0),
            "truncated": raw.get("truncated", False)
        }, stale_result=raw)

    def useless_fact(self) -> dict:
        """
        Get a random interesting fact from Useless Facts API.

        Returns:
            Dict with fact text and source URL
        """
        try:
            resp = httpx.get("https://uselessfacts.jsph.pl/random.json?language=en", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return self.success({
                "fact": data.get("text", ""),
                "source": data.get("source_url", ""),
                "source": data.get("source", "uselessfacts.jsph.pl")
            })
        except httpx.HTTPStatusError as e:
            return self.error(f"Useless Facts API error: {e}")
        except Exception as e:
            return self.error(f"Failed to fetch useless fact: {e}")

    def number_fact(self, number: int = None, fact_type: str = "trivia") -> dict:
        """
        Get a fact about a number from Numbers API.

        Args:
            number: Number to get fact about (default: random)
            fact_type: Type of fact — trivia, math, date, year (default: trivia)

        Returns:
            Dict with fact text, number, and type
        """
        try:
            if number is None:
                url = f"http://numbersapi.com/random/{fact_type}"
            else:
                url = f"http://numbersapi.com/{number}/{fact_type}"
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            return self.success({
                "fact": resp.text,
                "number": number,
                "type": fact_type
            })
        except httpx.HTTPStatusError as e:
            return self.error(f"Numbers API error: {e}")
        except Exception as e:
            return self.error(f"Failed to fetch number fact: {e}")

    def random_quote(self) -> dict:
        """
        Get a random quote from Quotable API.

        Returns:
            Dict with quote content, author, and tags
        """
        try:
            resp = httpx.get("https://api.quotable.io/random", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return self.success({
                "content": data.get("content", ""),
                "author": data.get("author", ""),
                "tags": data.get("tags", []),
                "authorSlug": data.get("authorSlug", "")
            })
        except httpx.HTTPStatusError as e:
            return self.error(f"Quotable API error: {e}")
        except Exception as e:
            return self.error(f"Failed to fetch quote: {e}")

    def wiki_random(self) -> dict:
        """
        Get a random Wikipedia article summary.

        Returns:
            Dict with title, extract, and URL
        """
        try:
            resp = httpx.get("https://en.wikipedia.org/api/rest_v1/page/random/summary", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return self.success({
                "title": data.get("title", ""),
                "extract": data.get("extract", ""),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                "lang": data.get("lang", "en")
            })
        except httpx.HTTPStatusError as e:
            return self.error(f"Wikipedia API error: {e}")
        except Exception as e:
            return self.error(f"Failed to fetch random Wikipedia article: {e}")

    def spacex_latest_launch(self) -> dict:
        """
        Get the latest SpaceX launch data.

        Returns:
            Dict with launch name, date, success status, and details
        """
        try:
            resp = httpx.get("https://api.spacexdata.com/v4/launches/latest", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return self.success({
                "name": data.get("name", ""),
                "date_utc": data.get("date_utc", ""),
                "success": data.get("success", None),
                "details": data.get("details", ""),
                "rocket": data.get("rocket", ""),
                "flight_number": data.get("flight_number", None)
            })
        except httpx.HTTPStatusError as e:
            return self.error(f"SpaceX API error: {e}")
        except Exception as e:
            return self.error(f"Failed to fetch SpaceX launch data: {e}")

    def jina_read(self, url: str) -> dict:
        """
        Read a URL and return clean markdown content via Jina Reader.

        Args:
            url: The URL to read

        Returns:
            Dict with markdown content and URL
        """
        try:
            jina_url = f"https://r.jina.ai/{url}"
            resp = httpx.get(jina_url, timeout=15)
            resp.raise_for_status()
            return self.success({
                "content": resp.text,
                "url": url
            })
        except httpx.HTTPStatusError as e:
            return self.error(f"Jina Reader error: {e}")
        except Exception as e:
            return self.error(f"Failed to read URL with Jina: {e}")

    def country_info(self, name: str = None) -> dict:
        """
        Get country information from REST Countries API.

        Args:
            name: Country name (optional, if not provided returns random country)

        Returns:
            Dict with country data including name, capital, region, population, etc.
        """
        try:
            if name:
                url = f"https://restcountries.com/v3.1/name/{name}"
            else:
                url = "https://restcountries.com/v3.1/all"
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return self.error(f"Country '{name}' not found" if name else "No countries found")
            if not name:
                data = [data[0]]  # Return just first country if all
            country = data[0]
            return self.success({
                "name": country.get("name", {}).get("common", ""),
                "official_name": country.get("name", {}).get("official", ""),
                "capital": country.get("capital", []),
                "region": country.get("region", ""),
                "subregion": country.get("subregion", ""),
                "population": country.get("population", 0),
                "area": country.get("area", 0),
                "languages": country.get("languages", {}),
                "currencies": country.get("currencies", {}),
                "flags": country.get("flags", {})
            })
        except httpx.HTTPStatusError as e:
            return self.error(f"REST Countries API error: {e}")
        except Exception as e:
            return self.error(f"Failed to fetch country info: {e}")

    def cratesio_info(self, crate_name: str) -> dict:
        """
        Get Rust crate information from crates.io API.

        Args:
            crate_name: Name of the Rust crate

        Returns:
            Dict with crate data including name, version, description, downloads, etc.
        """
        try:
            url = f"https://crates.io/api/v1/crates/{crate_name}"
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            crate = data.get("crate", {})
            return self.success({
                "name": crate.get("name", ""),
                "description": crate.get("description", ""),
                "max_version": crate.get("max_version", ""),
                "downloads": crate.get("downloads", 0),
                "recent_downloads": crate.get("recent_downloads", 0),
                "homepage": crate.get("homepage", ""),
                "repository": crate.get("repository", ""),
                "updated_at": crate.get("updated_at", "")
            })
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return self.error(f"Crate '{crate_name}' not found on crates.io")
            return self.error(f"crates.io API error: {e}")
        except Exception as e:
            return self.error(f"Failed to fetch crate info: {e}")

    def hackernews_search(self, query: str, limit: int = 10) -> dict:
        """
        Search Hacker News via Algolia API.

        Args:
            query: Search query
            limit: Maximum results to return (default 10)

        Returns:
            Dict with search results including title, url, points, author, etc.
        """
        try:
            url = f"http://hn.algolia.com/api/v1/search"
            params = {"query": query, "hitsPerPage": limit}
            resp = httpx.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", [])
            results = []
            for hit in hits:
                results.append({
                    "title": hit.get("title", ""),
                    "url": hit.get("url", ""),
                    "points": hit.get("points", 0),
                    "author": hit.get("author", ""),
                    "created_at": hit.get("created_at_i", 0),
                    "object_id": hit.get("objectID", "")
                })
            return self.success({
                "query": query,
                "count": len(results),
                "results": results
            })
        except httpx.HTTPStatusError as e:
            return self.error(f"Hacker News API error: {e}")
        except Exception as e:
            return self.error(f"Failed to search Hacker News: {e}")


# Module-level instance
_search = SearchTools()


# Backwards compat functions
def web_search(query: str, max_results: int = 5) -> dict:
    """
    Search the web via DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum results to return

    Returns:
        Dict with query, count, and results
    """
    return _search.web_search(query, max_results)


def news_search(query: str, max_results: int = 5) -> dict:
    """
    Search recent news via DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum results to return

    Returns:
        Dict with query, count, and results
    """
    return _search.news_search(query, max_results)


def wiki_lookup(topic: str) -> dict:
    """
    Look up a Wikipedia article summary.

    Args:
        topic: Topic to look up

    Returns:
        Dict with Wikipedia summary data
    """
    return _search.wiki_lookup(topic)


def reddit_search(query: str, subreddit: str = None, limit: int = 10) -> dict:
    """
    Search Reddit posts.

    Args:
        query: Search query
        subreddit: Optional subreddit to search within
        limit: Maximum results to return

    Returns:
        Dict with query, subreddit, count, and results
    """
    return _search.reddit_search(query, subreddit, limit)


def get_weather() -> dict:
    return _search.get_weather()


def get_weather_forecast(days: int = 3) -> dict:
    """
    Get weather forecast for South Florida.

    Args:
        days: Number of forecast days (1-7, default 3)

    Returns:
        Dict with daily forecast data
    """
    return _search.get_weather_forecast(days)


def get_pypi_stats(package: str = "openagent-directive") -> dict:
    """
    Get PyPI download statistics for a package.

    Args:
        package: Package name (default: "openagent-directive")

    Returns:
        Dict with last_day, last_week, last_month, total downloads
    """
    return _search.get_pypi_stats(package)


def get_recent_commits(username: str = None, repo: str = None, limit: int = 10) -> dict:
    """
    Get recent commits for GitHub repositories.

    Args:
        username: GitHub username (default: inferred from token)
        repo: Specific repository name (optional, e.g. "PrivyBot")
        limit: Number of commits to return (default: 10)

    Returns:
        Dict with commits array containing commit metadata
    """
    return _search.get_recent_commits(username, repo, limit)


def fetch_url(url: str, max_chars: int = 3000) -> dict:
    """
    Fetch and read the full text content of a web page.

    Args:
        url: The full URL to fetch including https:// prefix
        max_chars: Maximum characters to return (default 3000)

    Returns:
        Dict with url, title, content, char_count, truncated
    """
    return _search.fetch_url(url, max_chars)


def useless_fact() -> dict:
    """
    Get a random interesting fact from Useless Facts API.

    Returns:
        Dict with fact text and source URL
    """
    return _search.useless_fact()


def number_fact(number: int = None, fact_type: str = "trivia") -> dict:
    """
    Get a fact about a number from Numbers API.

    Args:
        number: Number to get fact about (default: random)
        fact_type: Type of fact — trivia, math, date, year (default: trivia)

    Returns:
        Dict with fact text, number, and type
    """
    return _search.number_fact(number, fact_type)


def random_quote() -> dict:
    """
    Get a random quote from Quotable API.

    Returns:
        Dict with quote content, author, and tags
    """
    return _search.random_quote()


def wiki_random() -> dict:
    """
    Get a random Wikipedia article summary.

    Returns:
        Dict with title, extract, and URL
    """
    return _search.wiki_random()


def spacex_latest_launch() -> dict:
    """
    Get the latest SpaceX launch data.

    Returns:
        Dict with launch name, date, success status, and details
    """
    return _search.spacex_latest_launch()


def jina_read(url: str) -> dict:
    """
    Read a URL and return clean markdown content via Jina Reader.

    Args:
        url: The URL to read

    Returns:
        Dict with markdown content and URL
    """
    return _search.jina_read(url)


def country_info(name: str = None) -> dict:
    """
    Get country information from REST Countries API.

    Args:
        name: Country name (optional, if not provided returns random country)

    Returns:
        Dict with country data including name, capital, region, population, etc.
    """
    return _search.country_info(name)


def cratesio_info(crate_name: str) -> dict:
    """
    Get Rust crate information from crates.io API.

    Args:
        crate_name: Name of the Rust crate

    Returns:
        Dict with crate data including name, version, description, downloads, etc.
    """
    return _search.cratesio_info(crate_name)


def hackernews_search(query: str, limit: int = 10) -> dict:
    """
    Search Hacker News via Algolia API.

    Args:
        query: Search query
        limit: Maximum results to return (default 10)

    Returns:
        Dict with search results including title, url, points, author, etc.
    """
    return _search.hackernews_search(query, limit)
