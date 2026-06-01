"""Tests for bot/router.py — /status live git HEAD.

Pytest-style. run_all() shim retained for verify.py compatibility.
"""

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


def test_status_reads_live_git_head():
    """Mock subprocess.run returning known hash. Assert get_live_commit returns it."""
    from bot.router import get_live_commit
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "abc1234\n"
    with patch("bot.router.subprocess.run", return_value=mock_result):
        assert get_live_commit() == "abc1234"


def test_status_git_failure_shows_unknown():
    """Mock subprocess.run raising exception. Assert get_live_commit returns 'unknown'."""
    from bot.router import get_live_commit
    with patch("bot.router.subprocess.run", side_effect=Exception("git not found")):
        assert get_live_commit() == "unknown"


# --- verify.py shim ---

def run_all() -> tuple[int, int]:
    passed, failed = 0, 0
    for fn in (test_status_reads_live_git_head, test_status_git_failure_shows_unknown):
        try:
            fn()
            print(f"✓ router: {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"✗ router: {fn.__name__}\n  {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    p, f = run_all()
    sys.exit(0 if f == 0 else 1)
