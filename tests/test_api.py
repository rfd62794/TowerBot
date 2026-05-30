"""Tests for tools/api/ raw clients — credentials and basic responses."""

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


@test("api: youtube credentials load without error")
def test_youtube_credentials():
    from api.google.youtube_api import _get_credentials
    try:
        creds = _get_credentials()
        assert creds is not None, "Credentials returned None"
    except FileNotFoundError as e:
        assert False, f"YouTube token file missing: {e}"


@test("api: steam_api get_owned_games returns list")
def test_steam_owned_games():
    from api.steam.steam_api import get_game_library
    result = get_game_library()
    assert "error" not in result, f"Steam API error: {result.get('error')}"
    assert "raw" in result, "Expected 'raw' key"
    assert isinstance(result["raw"], list), "Expected list of games"
    assert len(result["raw"]) > 0, "Expected non-empty game list"


@test("api: steamspy_api returns dict for known appid")
def test_steamspy():
    from api.steam.steamspy_api import get_app_details
    result = get_app_details(2780540)
    assert isinstance(result, dict), "Expected dict return"
    assert "error" not in result or "appid" in result, \
        f"Steamspy returned error: {result.get('error')}"


@test("api: itad_api returns result for known game")
def test_itad():
    from api.steam.itad_api import lookup_game
    result = lookup_game("Duckov")
    assert isinstance(result, dict), "Expected dict return"


@test("api: ddg_api search_web returns list")
def test_ddg():
    from api.web.ddg_api import search_web
    result = search_web("Python programming", max_results=3)
    assert isinstance(result, list), \
        f"Expected list, got {type(result)}"


@test("api: wikipedia_api get_summary returns dict")
def test_wikipedia():
    from api.web.wikipedia_api import get_summary
    result = get_summary("Python_(programming_language)")
    assert isinstance(result, dict), "Expected dict return"
    assert "found" in result or "summary" in result or "error" in result, \
        "Expected 'found', 'summary', or 'error' key"


@test("api: reddit_api search_reddit returns list")
def test_reddit():
    from api.web.reddit_api import search_reddit
    result = search_reddit("incremental games", limit=3)
    assert isinstance(result, list), \
        f"Expected list, got {type(result)}"


@test("api: weather_api get_current_weather returns dict")
def test_weather_api():
    from api.weather.weather_api import get_current_weather
    result = get_current_weather()
    assert isinstance(result, dict), "Expected dict return"
    assert "error" not in result or "temp_f" in result, \
        f"Weather API returned error: {result.get('error')}"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
