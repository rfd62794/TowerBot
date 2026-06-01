"""Tests for bot/router.py — /status live git HEAD."""

import sys
import os
from unittest.mock import patch, MagicMock

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Stub heavy dependencies before importing bot.router
for _mod in ("bot.agent", "bot.model_manager", "bot.report",
             "infra.rate_limits", "infra.polling"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


def test_decorator(name):
    def wrapper(fn):
        fn.__name__ = name
        TESTS.append((name, fn))
        return fn
    return wrapper

test = test_decorator

TESTS = []


@test("router: get_live_commit returns hash from git")
def test_status_reads_live_git_head():
    """Mock subprocess.run returning known hash. Assert get_live_commit returns it."""
    from bot.router import get_live_commit
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "abc1234\n"
    with patch("bot.router.subprocess.run", return_value=mock_result):
        result = get_live_commit()
        assert result == "abc1234"


@test("router: get_live_commit returns unknown on git failure")
def test_status_git_failure_shows_unknown():
    """Mock subprocess.run raising exception. Assert get_live_commit returns 'unknown'."""
    from bot.router import get_live_commit
    with patch("bot.router.subprocess.run", side_effect=Exception("git not found")):
        result = get_live_commit()
        assert result == "unknown"


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


if __name__ == "__main__":
    passed, failed = run_all()
    print(f"\n{passed}/{passed + failed} passed.", end=" ")
    if failed == 0:
        print("Deploy safe.")
        sys.exit(0)
    else:
        print("Deploy blocked.")
        sys.exit(1)
