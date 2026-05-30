"""Tests for tools/youtube/ package — channel, videos, discovery."""

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


@test("youtube: channel summary returns views > 0")
def test_channel_summary():
    from tools.youtube import get_channel_summary
    result = get_channel_summary(days=7)
    assert "error" not in result, f"Channel summary error: {result.get('error')}"
    assert result.get("views", 0) > 0, f"Expected views > 0, got {result.get('views')}"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: channel summary has required keys")
def test_channel_summary_keys():
    from tools.youtube import get_channel_summary
    result = get_channel_summary(days=7)
    assert "error" not in result, f"Channel summary error: {result.get('error')}"
    for key in ("views", "watch_time_minutes", "subscribers_gained",
                "start_date", "end_date", "period_days"):
        assert key in result, f"Missing key: {key}"


@test("youtube: top videos returns list")
def test_top_videos():
    from tools.youtube import get_top_videos
    result = get_top_videos(days=28)
    assert "error" not in result, f"Top videos error: {result.get('error')}"
    assert "videos" in result, "Expected 'videos' key"
    assert isinstance(result["videos"], list), "Expected list"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: top videos has titles not just IDs")
def test_top_videos_titles():
    from tools.youtube import get_top_videos
    from core.db.schema import _exec
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
    from tools.youtube import get_video_analytics
    result = get_video_analytics("yZMuKQ2WEWA", days=28)
    assert "error" not in result, f"Video analytics error: {result.get('error')}"
    assert result.get("views", 0) > 0, f"Expected views > 0, got {result.get('views')}"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: video analytics handles unknown video (null safety)")
def test_video_analytics_null_safe():
    from tools.youtube import get_video_analytics
    result = get_video_analytics("FAKEID_xyz_verify_999", days=28)
    assert isinstance(result, dict), \
        f"Expected dict, got {type(result)}"
    assert "error" in result or "views" in result, \
        "Must return dict with 'error' or 'views' — never raise"


@test("youtube: traffic sources returns list")
def test_traffic_sources():
    from tools.youtube import get_traffic_sources
    result = get_traffic_sources(days=28)
    assert "error" not in result, f"Traffic sources error: {result.get('error')}"
    assert "top_search_terms" in result, "Expected 'top_search_terms' key"
    assert isinstance(result["top_search_terms"], list), "Expected list"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: demographics returns age and gender")
def test_demographics():
    from tools.youtube import get_audience_demographics
    result = get_audience_demographics(days=28)
    assert "error" not in result, f"Demographics error: {result.get('error')}"
    assert "age_groups" in result, "Expected 'age_groups' key"
    assert "gender" in result, "Expected 'gender' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: retention curve returns curve key")
def test_retention_curve():
    from tools.youtube import get_retention_curve
    result = get_retention_curve("yZMuKQ2WEWA", days=28)
    assert "error" not in result, f"Retention curve error: {result.get('error')}"
    assert "curve" in result, "Expected 'curve' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: device breakdown returns devices")
def test_device_breakdown():
    from tools.youtube import get_device_breakdown
    result = get_device_breakdown(days=28)
    assert "error" not in result, f"Device breakdown error: {result.get('error')}"
    assert "devices" in result, "Expected 'devices' key"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: daily views returns days list")
def test_daily_views():
    from tools.youtube import get_daily_views
    result = get_daily_views(days=28)
    assert "error" not in result, f"Daily views error: {result.get('error')}"
    assert "days" in result, "Expected 'days' key"
    assert len(result["days"]) > 0, "Expected at least one day of data"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("youtube: geographic breakdown returns countries")
def test_geographic_breakdown():
    from tools.youtube import get_geographic_breakdown
    result = get_geographic_breakdown(days=28)
    assert "error" not in result, f"Geographic breakdown error: {result.get('error')}"
    assert "countries" in result, "Expected 'countries' key"
    assert len(result["countries"]) > 0, "Expected at least one country"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
