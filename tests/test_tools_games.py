"""Tests for tools/games.py — game metrics, resolve, sale info, cache."""

import sys
import os
import time

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


@test("games: Duckov resolves by name")
def test_duckov_resolves():
    from tools.games.metrics import get_game_metrics
    result = get_game_metrics("Duckov")
    assert "error" not in result, f"Game metrics error: {result.get('error')}"
    assert result.get("name") is not None, "Expected game name"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("games: unknown game returns error dict (not exception)")
def test_unknown_game_safe():
    from tools.games.metrics import get_game_metrics
    result = get_game_metrics("fakegamexyz99999verify")
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "error" in result, \
        "Expected 'error' key for unknown game — never raise"
    assert result.get("ok") == False, "Expected ok=False for error"


@test("games: installed games library returns 100+ games")
def test_installed_games():
    from tools.api.steam_api import get_game_library
    result = get_game_library()
    assert "error" not in result, f"Steam library error: {result.get('error')}"
    games = result["raw"]
    assert len(games) > 100, f"Expected 100+ games, got {len(games)}"


@test("games: sale info returns games list")
def test_sale_info():
    from tools.games.metrics import get_sale_info
    result = get_sale_info(["Scritchy Scratchy"])
    assert "games" in result, "Expected 'games' key in result"
    assert len(result["games"]) > 0, "Expected at least one game result"
    assert result.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result, "Expected stale_notice key"


@test("games: resolve_appid returns dict with appid")
def test_resolve_appid():
    from tools.games.metrics import resolve_appid
    result = resolve_appid("Raccoin")
    assert result is not None, "Expected non-None for known game"
    assert "appid" in result, "Expected 'appid' key"
    assert isinstance(result["appid"], int), "Expected int appid"


@test("games: second call to get_game_metrics returns from cache")
def test_game_metrics_cache():
    from tools.games.metrics import get_game_metrics
    result1 = get_game_metrics("Duckov")
    assert "error" not in result1, f"First call failed: {result1.get('error')}"
    result2 = get_game_metrics("Duckov")
    assert "error" not in result2, f"Second call failed: {result2.get('error')}"
    assert result1["appid"] == result2["appid"], \
        "Cache returned different appid on second call"
    assert result2.get("ok") == True, "Expected ok=True"
    assert "stale_notice" in result2, "Expected stale_notice key"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
