"""Tests for tools/search_tools.py — web, news, wiki, reddit, weather."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from core.db import init_db
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
    from tools.search_tools import web_search
    result = web_search("Python programming", max_results=3)
    assert "count" in result, "Expected 'count' key"
    assert result["count"] >= 0, "Expected count >= 0"
    assert "results" in result, "Expected 'results' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("search: news_search returns count >= 0")
def test_news_search():
    from tools.search_tools import news_search
    result = news_search("technology", max_results=3)
    assert "count" in result, "Expected 'count' key"
    assert result["count"] >= 0, "Expected count >= 0"
    assert "results" in result, "Expected 'results' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("search: wiki_lookup finds Python article")
def test_wiki_lookup_found():
    from tools.search_tools import wiki_lookup
    result = wiki_lookup("Python_(programming_language)")
    assert isinstance(result, dict), "Expected dict return"
    assert "found" in result, "Expected 'found' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("search: wiki_lookup handles unknown topic (not exception)")
def test_wiki_lookup_not_found():
    from tools.search_tools import wiki_lookup
    result = wiki_lookup("xkq9fake99topicverify999")
    assert isinstance(result, dict), \
        f"Expected dict, got {type(result)}"
    assert "found" in result, "Expected 'found' key — never raise"
    assert result["found"] is False, \
        "Expected found=False for unknown topic"
    assert result.get("ok") == True, "Expected ok=True (found=False is valid)"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("search: reddit_search returns count >= 0")
def test_reddit_search():
    from tools.search_tools import reddit_search
    result = reddit_search("incremental games", limit=5)
    assert "count" in result, "Expected 'count' key"
    assert result["count"] >= 0, "Expected count >= 0"
    assert "results" in result, "Expected 'results' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("search: get_weather returns temp_f")
def test_weather():
    from tools.search_tools import get_weather
    result = get_weather()
    assert "error" not in result, f"Weather error: {result.get('error')}"
    assert "temp_f" in result, "Expected 'temp_f' key"
    assert "stale_notice" in result, "Expected 'stale_notice' key"


@test("search: get_weather records to weather_history")
def test_weather_history():
    from tools.search_tools import get_weather
    from core.db import get_weather_history
    from datetime import datetime
    result = get_weather()
    assert "error" not in result, f"Weather call failed: {result.get('error')}"
    today = datetime.now().strftime("%Y-%m-%d")
    history = get_weather_history(days=1)
    assert len(history) > 0, "Weather history empty after get_weather call"
    assert history[0]["date"] == today, \
        f"Expected today {today}, got {history[0]['date']}"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
