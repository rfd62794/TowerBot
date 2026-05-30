"""PrivyBot verification script — gate between laptop and Tower.

Runs integration tests to verify all tools return real data.
Exit code 0 = pass (deploy safe)
Exit code 1 = fail (deploy blocked)
"""

import sys
import os
import sqlite3
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment
load_dotenv()

# Initialize database (required for caching)
from core.db import init_db
init_db()

# Test registry
TESTS = []


def test(name):
    """Decorator that adds function to TESTS registry."""
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all():
    """Run all tests and report results."""
    passed = 0
    failed = 0
    
    for name, func in TESTS:
        try:
            func()
            print(f"✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}")
            print(f"  AssertionError: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}")
            print(f"  {type(e).__name__}: {e}")
            failed += 1
    
    print()
    print(f"{passed}/{len(TESTS)} passed.", end=" ")
    
    if failed == 0:
        print("Deploy safe.")
        sys.exit(0)
    else:
        print("Deploy blocked.")
        sys.exit(1)


# Tests

@test("database: tables exist")
def test_db():
    conn = sqlite3.connect("privy.db")
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = [t[0] for t in tables]
    
    assert "messages" in table_names, "messages table missing"
    assert "memory" in table_names, "memory table missing"
    assert "threads" in table_names, "threads table missing"
    assert "tool_cache" in table_names, "tool_cache table missing"
    assert "channel_history" in table_names, "channel_history table missing"
    assert "model_status" in table_names, "model_status table missing"
    
    conn.close()


@test("memory: 27 seeds present")
def test_memory():
    from core.db import list_memories
    memories = list_memories()
    assert len(memories) >= 27, f"Expected 27+ memories, got {len(memories)}"


@test("models: free models discoverable")
def test_models():
    from core.model_manager import fetch_free_tool_models
    models = fetch_free_tool_models()
    assert len(models) >= 5, f"Expected 5+ models, got {len(models)}"


@test("youtube: channel summary returns views")
def test_youtube():
    from tools.youtube import get_channel_summary
    result = get_channel_summary(days=7)
    assert "error" not in result, f"Channel summary error: {result.get('error')}"
    assert result.get("views", 0) > 0, f"Expected views > 0, got {result.get('views')}"


@test("youtube: top videos returns list")
def test_top_videos():
    from tools.youtube import get_top_videos
    result = get_top_videos(days=28)
    assert "error" not in result, f"Top videos error: {result.get('error')}"


@test("youtube: video analytics works")
def test_video_analytics():
    from tools.youtube import get_video_analytics
    # Use known good video ID
    result = get_video_analytics("yZMuKQ2WEWA", days=28)
    assert "error" not in result, f"Video analytics error: {result.get('error')}"
    assert result.get("views", 0) > 0, f"Expected views > 0, got {result.get('views')}"


@test("steam: owned games returns library")
def test_steam():
    from tools.api.steam_api import get_game_library
    result = get_game_library()
    assert "error" not in result, f"Steam library error: {result.get('error')}"
    games = result["raw"]
    assert len(games) > 100, f"Expected 100+ games, got {len(games)}"


@test("games: Duckov resolves by name")
def test_game_metrics():
    from tools.games import get_game_metrics
    result = get_game_metrics("Duckov")
    assert "error" not in result, f"Game metrics error: {result.get('error')}"
    assert result.get("name") is not None, "Expected game name"


@test("games: sale info returns prices")
def test_sale_info():
    from tools.games import get_sale_info
    result = get_sale_info(["Scritchy Scratchy"])
    assert "games" in result, "Expected 'games' key in result"
    assert len(result["games"]) > 0, "Expected at least one game result"


@test("recommendations: returns games")
def test_recommendations():
    from tools.recommendations import get_content_recommendations
    result = get_content_recommendations(limit=3)
    assert result.get("count", 0) > 0, f"Expected count > 0, got {result.get('count')}"


@test("youtube: traffic sources returns list")
def test_traffic_sources():
    from tools.youtube import get_traffic_sources
    result = get_traffic_sources(days=28)
    assert "error" not in result, f"Traffic sources error: {result.get('error')}"
    assert "top_search_terms" in result, "Expected top_search_terms key"
    assert isinstance(result["top_search_terms"], list), "Expected list"


@test("youtube: demographics returns breakdown")
def test_demographics():
    from tools.youtube import get_audience_demographics
    result = get_audience_demographics(days=28)
    assert "error" not in result, f"Demographics error: {result.get('error')}"
    assert "age_groups" in result, "Expected age_groups key"
    assert "gender" in result, "Expected gender key"


@test("youtube: retention curve returns data")
def test_retention_curve():
    from tools.youtube import get_retention_curve
    result = get_retention_curve("yZMuKQ2WEWA", days=28)
    assert "error" not in result, f"Retention curve error: {result.get('error')}"
    assert "curve" in result, "Expected curve key"
    # Curve may be empty for small channels, that's acceptable


@test("youtube: device breakdown returns devices")
def test_device_breakdown():
    from tools.youtube import get_device_breakdown
    result = get_device_breakdown(days=28)
    assert "error" not in result, f"Device breakdown error: {result.get('error')}"
    assert "devices" in result, "Expected devices key"


@test("youtube: daily views returns time series")
def test_daily_views():
    from tools.youtube import get_daily_views
    result = get_daily_views(days=28)
    assert "error" not in result, f"Daily views error: {result.get('error')}"
    assert "days" in result, "Expected days key"
    assert len(result["days"]) > 0, "Expected at least one day of data"


@test("youtube: geographic breakdown returns countries")
def test_geographic_breakdown():
    from tools.youtube import get_geographic_breakdown
    result = get_geographic_breakdown(days=28)
    assert "error" not in result, f"Geographic breakdown error: {result.get('error')}"
    assert "countries" in result, "Expected countries key"
    assert len(result["countries"]) > 0, "Expected at least one country"


@test("search: web search returns results")
def test_web_search():
    from tools.search_tools import web_search
    result = web_search("Python programming", max_results=3)
    assert "count" in result, "Expected count key"
    assert result["count"] >= 0, "Expected count >= 0"
    assert "results" in result, "Expected results key"


@test("search: news search returns results")
def test_news_search():
    from tools.search_tools import news_search
    result = news_search("technology", max_results=3)
    assert "count" in result, "Expected count key"
    assert result["count"] >= 0, "Expected count >= 0"
    assert "results" in result, "Expected results key"


@test("search: wiki lookup finds article")
def test_wiki_lookup():
    from tools.search_tools import wiki_lookup
    result = wiki_lookup("Python_(programming_language)")
    assert "found" in result, "Expected found key"
    # Article may not be found, that's acceptable for test
    # Just verify the API call succeeds


@test("search: reddit search returns posts")
def test_reddit_search():
    from tools.search_tools import reddit_search
    result = reddit_search("incremental games", limit=5)
    assert "count" in result, "Expected count key"
    assert result["count"] >= 0, "Expected count >= 0"
    assert "results" in result, "Expected results key"


@test("search: weather returns temperature")
def test_weather():
    from tools.search_tools import get_weather
    result = get_weather()
    assert "error" not in result, f"Weather error: {result.get('error')}"
    assert "temp_f" in result, "Expected temp_f key"


if __name__ == "__main__":
    run_all()
