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


if __name__ == "__main__":
    run_all()
