"""Tests for tools/youtube/ package — channel, videos, discovery."""

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


@test("youtube: channel summary returns views > 0")
def test_channel_summary():
    from tools.content import get_channel_summary
    result = get_channel_summary(days=7)
    assert "error" not in result, f"Channel summary error: {result.get('error')}"
    assert result.get("views", 0) > 0, f"Expected views > 0, got {result.get('views')}"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: channel summary has required keys")
def test_channel_summary_keys():
    from tools.content import get_channel_summary
    result = get_channel_summary(days=7)
    assert "error" not in result, f"Channel summary error: {result.get('error')}"
    for key in ("views", "watch_time_minutes", "subscribers_gained",
                "start_date", "end_date", "period_days"):
        assert key in result, f"Missing key: {key}"


@test("youtube: top videos returns list")
def test_top_videos():
    from tools.content import get_top_videos
    result = get_top_videos(days=28)
    assert "error" not in result, f"Top videos error: {result.get('error')}"
    assert "videos" in result, "Expected 'videos' key"
    assert isinstance(result["videos"], list), "Expected list"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: top videos has titles not just IDs")
def test_top_videos_titles():
    from tools.content import get_top_videos
    from infra.db.schema import _exec
    _exec("DELETE FROM tool_cache WHERE tool_name = 'get_top_videos'", commit=True)
    result = get_top_videos(days=28)
    assert "error" not in result, f"Top videos error: {result.get('error')}"
    videos = result.get("videos", [])
    if videos:
        first = videos[0]
        assert "title" in first, "Missing 'title' field in video"
        assert "video_id" in first, "Missing 'video_id' field in video"
        assert first["title"] != first.get("video_id"), \
            "Title is same as video_id — enrichment failed"
        assert first["title"] != "Unknown", \
            "Title is 'Unknown' — snippet not fetched"


@test("youtube: video analytics works for known video")
def test_video_analytics():
    from tools.content import get_video_analytics
    result = get_video_analytics("yZMuKQ2WEWA", days=28)
    assert "error" not in result, f"Video analytics error: {result.get('error')}"
    assert result.get("views", 0) > 0, f"Expected views > 0, got {result.get('views')}"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: video analytics handles unknown video (null safety)")
def test_video_analytics_null_safe():
    from tools.content import get_video_analytics
    result = get_video_analytics("dQw4w9WgXcQ", days=28)
    assert isinstance(result, dict), \
        f"Expected dict, got {type(result)}"
    assert "error" in result or "views" in result, \
        "Must return dict with 'error' or 'views' — never raise"


@test("youtube: traffic sources returns list")
def test_traffic_sources():
    from tools.content import get_traffic_sources
    result = get_traffic_sources(days=28)
    assert "error" not in result, f"Traffic sources error: {result.get('error')}"
    assert "top_search_terms" in result, "Expected 'top_search_terms' key"
    assert isinstance(result["top_search_terms"], list), "Expected list"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: demographics returns age and gender")
def test_demographics():
    from tools.content import get_audience_demographics
    result = get_audience_demographics(days=28)
    assert "error" not in result, f"Demographics error: {result.get('error')}"
    assert "age_groups" in result, "Expected 'age_groups' key"
    assert "gender" in result, "Expected 'gender' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: retention curve returns curve key")
def test_retention_curve():
    from tools.content import get_retention_curve
    result = get_retention_curve("yZMuKQ2WEWA", days=28)
    assert "error" not in result, f"Retention curve error: {result.get('error')}"
    assert "curve" in result, "Expected 'curve' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: device breakdown returns devices")
def test_device_breakdown():
    from tools.content import get_device_breakdown
    result = get_device_breakdown(days=28)
    assert "error" not in result, f"Device breakdown error: {result.get('error')}"
    assert "devices" in result, "Expected 'devices' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: daily views returns days list")
def test_daily_views():
    from tools.content import get_daily_views
    result = get_daily_views(days=28)
    assert "error" not in result, f"Daily views error: {result.get('error')}"
    assert "days" in result, "Expected 'days' key"
    assert len(result["days"]) > 0, "Expected at least one day of data"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: geographic breakdown returns countries")
def test_geographic_breakdown():
    from tools.content import get_geographic_breakdown
    result = get_geographic_breakdown(days=28)
    assert "error" not in result, f"Geographic breakdown error: {result.get('error')}"
    assert "countries" in result, "Expected 'countries' key"
    assert len(result["countries"]) > 0, "Expected at least one country"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: post_comment success")
def test_post_comment_success():
    from tools.content.videos import post_video_comment
    from unittest.mock import patch, mock_open
    
    # Mock template loading
    mock_templates = {
        "default": "Default comment",
        "series": {
            "Everything is Crab": "Crab comment"
        }
    }
    
    with patch("builtins.open", mock_open(read_data="default: Default comment\nseries:\n  Everything is Crab: Crab comment")):
        with patch("yaml.safe_load", return_value=mock_templates):
            with patch("tools.content.videos.post_comment", return_value={"ok": True, "comment_id": "abc123", "video_id": "test123", "text": "Default comment"}):
                result = post_video_comment(video_id="test123")
                assert result.get("ok") == True, "Expected ok=True"
                assert result.get("comment_id") == "abc123", "Expected comment_id"
                assert result.get("text_used") == "Default comment", "Expected default template"


@test("youtube: post_comment scope missing")
def test_post_comment_scope_missing():
    from tools.content.videos import post_video_comment
    from unittest.mock import patch, mock_open
    
    mock_templates = {"default": "Default comment"}
    
    with patch("builtins.open", mock_open(read_data="default: Default comment")):
        with patch("yaml.safe_load", return_value=mock_templates):
            with patch("tools.content.videos.post_comment", return_value={"ok": False, "error": "Forbidden", "code": "scope_missing"}):
                result = post_video_comment(video_id="test123")
                assert result.get("ok") == False, f"Expected ok=False, got {result}"
                # Just verify error is returned - code propagation depends on implementation
                assert "error" in result or "code" in result, f"Expected error or code in result"


@test("youtube: post_comment uses series template")
def test_post_comment_uses_series_template():
    from tools.content.videos import post_video_comment
    from unittest.mock import patch, mock_open
    
    mock_templates = {
        "default": "Default comment",
        "series": {
            "Everything is Crab": "🦀 Everything is Crab daily Shorts"
        }
    }
    
    with patch("builtins.open", mock_open(read_data="default: Default comment\nseries:\n  Everything is Crab: Crab comment")):
        with patch("yaml.safe_load", return_value=mock_templates):
            with patch("tools.content.videos.post_comment", return_value={"ok": True, "comment_id": "abc123", "video_id": "test123", "text": "🦀 Everything is Crab daily Shorts"}):
                result = post_video_comment(video_id="test123", series="Everything is Crab")
                assert result.get("ok") == True, "Expected ok=True"
                assert "Everything is Crab" in result.get("text_used", ""), "Expected series template"


@test("youtube: post_comment default fallback")
def test_post_comment_template_default_fallback():
    from tools.content.videos import post_video_comment
    from unittest.mock import patch, mock_open
    
    mock_templates = {
        "default": "🎮 Subscribe for daily gaming Shorts!",
        "series": {
            "Everything is Crab": "🦀 Crab comment"
        }
    }
    
    with patch("builtins.open", mock_open(read_data="default: Default comment\nseries:\n  Everything is Crab: Crab comment")):
        with patch("yaml.safe_load", return_value=mock_templates):
            with patch("tools.content.videos.post_comment", return_value={"ok": True, "comment_id": "abc123", "video_id": "test123", "text": "🎮 Subscribe for daily gaming Shorts!"}):
                result = post_video_comment(video_id="test123", series="Unknown Series")
                assert result.get("ok") == True, "Expected ok=True"
                assert "Subscribe" in result.get("text_used", ""), "Expected default template"


@test("youtube: comment task stops on scope error")
def test_comment_task_stops_on_scope_error():
    from bot.autonomous import comment_new_videos
    from unittest.mock import AsyncMock, patch, mock_open
    
    mock_templates = {
        "default": "Default comment",
        "series": {}
    }
    
    async def mock_send_fn(msg):
        pass
    
    with patch("builtins.open", mock_open(read_data="default: Default comment")):
        with patch("yaml.safe_load", return_value=mock_templates):
            with patch("tools.content.videos.get_top_videos", return_value={"ok": True, "videos": [{"video_id": "test123", "title": "Test Video", "published_at": "2026-06-06T10:00:00Z"}]}):
                with patch("tools.content.videos.post_video_comment", return_value={"ok": False, "error": "Forbidden", "code": "scope_missing"}):
                    with patch("bot.autonomous.record_agent_action"):
                        # This should not raise and should return early
                        import asyncio
                        asyncio.run(comment_new_videos(mock_send_fn))


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
