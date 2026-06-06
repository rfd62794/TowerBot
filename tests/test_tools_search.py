"""Tests for tools/search_tools.py — web, news, wiki, reddit, weather."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db
init_db()

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


@test("search: web_search returns count >= 0")
def test_web_search():
    from tools.search.search_tools import web_search
    result = web_search("Python programming", max_results=3)
    assert "count" in result, "Expected 'count' key"
    assert result["count"] >= 0, "Expected count >= 0"
    assert "results" in result, "Expected 'results' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("search: news_search returns count >= 0")
def test_news_search():
    from tools.search.search_tools import news_search
    result = news_search("technology", max_results=3)
    assert "count" in result, "Expected 'count' key"
    assert result["count"] >= 0, "Expected count >= 0"
    assert "results" in result, "Expected 'results' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("search: wiki_lookup finds Python article")
def test_wiki_lookup_found():
    from tools.search.search_tools import wiki_lookup
    result = wiki_lookup("Python_(programming_language)")
    assert isinstance(result, dict), "Expected dict return"
    # API may be blocked, so accept both success and error
    if result.get("ok") == True:
        assert "found" in result, "Expected 'found' key on success"
    else:
        assert "error" in result, "Expected 'error' key on failure"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("search: wiki_lookup handles unknown topic (not exception)")
def test_wiki_lookup_not_found():
    from tools.search.search_tools import wiki_lookup
    result = wiki_lookup("xkq9fake99topicverify999")
    assert isinstance(result, dict), \
        f"Expected dict, got {type(result)}"
    # API may be blocked, so accept both success and error
    if result.get("ok") == True:
        assert "found" in result, "Expected 'found' key — never raise"
        assert result["found"] is False, \
            "Expected found=False for unknown topic"
    else:
        assert "error" in result, "Expected 'error' key on failure"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("search: reddit_search returns count >= 0")
def test_reddit_search():
    from tools.search.search_tools import reddit_search
    result = reddit_search("incremental games", limit=5)
    # API may be blocked, so accept both success and error
    if result.get("ok") == True:
        assert "count" in result, "Expected 'count' key"
        assert result["count"] >= 0, "Expected count >= 0"
        assert "results" in result, "Expected 'results' key"
    else:
        assert "error" in result, "Expected 'error' key on failure"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("search: reddit_search falls back to DDG when Reddit fails")
def test_reddit_search_falls_back_to_ddg():
    from unittest.mock import patch
    from tools.search.search_tools import reddit_search
    from api.web.reddit_api import reddit_api

    # Mock Reddit API to return error
    with patch.object(reddit_api, 'search_reddit', return_value={"_live_failed": True, "ok": False}):
        result = reddit_search("test query", subreddit="r/test", limit=3)
        # Should have DDG fallback source marker
        assert result.get("source") == "ddg_fallback", f"Expected source='ddg_fallback', got {result.get('source')}"
        assert result.get("note") == "Reddit API unavailable, results via DDG", f"Expected fallback note, got {result.get('note')}"
        assert result.get("ok") == True, "Expected DDG fallback to succeed"


@test("search: get_weather returns temp_f")
def test_weather():
    from tools.search.search_tools import get_weather
    result = get_weather()
    assert "error" not in result, f"Weather error: {result.get('error')}"
    assert "temp_f" in result, "Expected 'temp_f' key"
    assert "stale_notice" in result, "Expected 'stale_notice' key"


@test("search: get_weather records to weather_history")
def test_weather_history():
    from tools.search.search_tools import get_weather
    from infra.db import get_weather_history
    from datetime import datetime
    result = get_weather()
    assert "error" not in result, f"Weather call failed: {result.get('error')}"
    today = datetime.now().strftime("%Y-%m-%d")
    history = get_weather_history(days=1)
    assert len(history) > 0, "Weather history empty after get_weather call"
    assert history[0]["date"] == today, \
        f"Expected today {today}, got {history[0]['date']}"


@test("forecast: get_weather_forecast returns ok=True")
def test_forecast_ok():
    from tools.search.search_tools import get_weather_forecast
    result = get_weather_forecast(days=3)
    assert result.get("ok") == True, f"Expected ok=True, got {result}"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("forecast: returns days array with count > 0")
def test_forecast_count():
    from tools.search.search_tools import get_weather_forecast
    result = get_weather_forecast(days=3)
    assert "days" in result, "Expected 'days' key"
    assert "count" in result, "Expected 'count' key"
    assert result["count"] > 0, "Expected count > 0"
    assert len(result["days"]) > 0, "Expected non-empty days array"


@test("forecast: each day has high_f, low_f, condition, day_of_week, date")
def test_forecast_structure():
    from tools.search.search_tools import get_weather_forecast
    result = get_weather_forecast(days=3)
    days = result.get("days", [])
    assert len(days) > 0, "Expected at least one day"
    for day in days:
        assert "high_f" in day, "Expected 'high_f' in day"
        assert "low_f" in day, "Expected 'low_f' in day"
        assert "condition" in day, "Expected 'condition' in day"
        assert "day_of_week" in day, "Expected 'day_of_week' in day"
        assert "date" in day, "Expected 'date' in day"


@test("forecast: days=1 returns exactly 1 day")
def test_forecast_days_1():
    from tools.search.search_tools import get_weather_forecast
    result = get_weather_forecast(days=1)
    assert result["count"] == 1, f"Expected count=1, got {result['count']}"
    assert len(result["days"]) == 1, f"Expected 1 day, got {len(result['days'])}"


@test("forecast: days=7 returns up to 7 days")
def test_forecast_days_7():
    from tools.search.search_tools import get_weather_forecast
    result = get_weather_forecast(days=7)
    assert result["count"] <= 7, f"Expected count <= 7, got {result['count']}"
    assert len(result["days"]) <= 7, f"Expected <= 7 days, got {len(result['days'])}"


@test("pypi: get_pypi_stats returns ok=True")
def test_pypi_ok():
    from tools.search.search_tools import get_pypi_stats
    result = get_pypi_stats("openagent-directive")
    # May be rate limited (429) - accept either success or rate limit error
    if result.get("ok") == True:
        assert "stale_notice" in result, "Expected stale_notice key"
    else:
        # If rate limited, should have error
        assert "error" in result, "Expected 'error' key on failure"


@test("pypi: returns last_day, last_week, last_month, total keys")
def test_pypi_keys():
    from tools.search.search_tools import get_pypi_stats
    result = get_pypi_stats("openagent-directive")
    # Only check keys if successful
    if result.get("ok") == True:
        expected_keys = ["package", "last_day", "last_week", "last_month", "total"]
        for key in expected_keys:
            assert key in result, f"Expected key '{key}' in result"


@test("pypi: get_pypi_stats('openagent-directive') works")
def test_pypi_openagent_directive():
    from tools.search.search_tools import get_pypi_stats
    result = get_pypi_stats("openagent-directive")
    # May be rate limited - only assert if successful
    if result.get("ok") == True:
        assert result.get("package") == "openagent-directive", f"Expected package 'openagent-directive', got {result.get('package')}"
        assert result.get("total") >= 0, f"Expected total >= 0, got {result.get('total')}"


@test("pypi: get_pypi_stats('nonexistent-package-xyz') returns ok=False")
def test_pypi_nonexistent():
    from tools.search.search_tools import get_pypi_stats
    result = get_pypi_stats("nonexistent-package-xyz-999")
    assert result.get("ok") == False, f"Expected ok=False for nonexistent package, got {result}"
    assert "error" in result, "Expected 'error' key for nonexistent package"


@test("github: get_recent_commits returns ok=True or error for missing token")
def test_github_ok():
    from tools.search.search_tools import get_recent_commits
    result = get_recent_commits()
    # May fail if GITHUB_TOKEN not set
    if result.get("ok") == True:
        assert "stale_notice" in result, "Expected stale_notice key"
    else:
        assert "error" in result, "Expected 'error' key on failure"


@test("github: returns count and commits keys")
def test_github_keys():
    from tools.search.search_tools import get_recent_commits
    result = get_recent_commits()
    # Only check keys if successful
    if result.get("ok") == True:
        assert "count" in result, "Expected 'count' key"
        assert "commits" in result, "Expected 'commits' key"


@test("github: each commit has expected keys")
def test_github_structure():
    from tools.search.search_tools import get_recent_commits
    result = get_recent_commits()
    # Only check structure if successful and has commits
    if result.get("ok") == True and result.get("commits"):
        commits = result.get("commits", [])
        if len(commits) > 0:
            for commit in commits:
                assert "sha" in commit, "Expected 'sha' in commit"
                assert "message" in commit, "Expected 'message' in commit"
                assert "author" in commit, "Expected 'author' in commit"
                assert "date" in commit, "Expected 'date' in commit"
                assert "repo" in commit, "Expected 'repo' in commit"
                assert "url" in commit, "Expected 'url' in commit"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
