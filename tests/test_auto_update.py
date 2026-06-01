"""Tests for auto-update system."""

import sys
import os
import subprocess
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def test_decorator(name):
    def wrapper(fn):
        fn.__name__ = name
        TESTS.append((name, fn))
        return fn
    return wrapper

test = test_decorator

TESTS = []


@test("auto-update: trigger_restart spawns detached PowerShell")
def test_trigger_restart():
    """Test that trigger_restart spawns detached PowerShell processes."""
    from scripts.update import trigger_restart
    with patch("subprocess.Popen") as mock_popen:
        trigger_restart()
        assert mock_popen.call_count == 2
        # First call should be PrivyBot
        args = mock_popen.call_args_list[0][0][0]
        assert "powershell" in args
        assert "net stop PrivyBot" in " ".join(args)
        assert "net start PrivyBot" in " ".join(args)


@test("auto-update: skips on dev instance")
def test_skips_on_dev_instance():
    """Test that check_for_updates skips when INSTANCE_ROLE is not production."""
    original_role = os.environ.get("INSTANCE_ROLE")
    try:
        os.environ["INSTANCE_ROLE"] = "development"
        import importlib
        import scripts.update
        importlib.reload(scripts.update)
        send_fn = AsyncMock()
        result = asyncio.run(scripts.update.check_for_updates(send_fn))
        assert result == "DONE: Skipped — not production instance"
    finally:
        if original_role is None:
            os.environ.pop("INSTANCE_ROLE", None)
        else:
            os.environ["INSTANCE_ROLE"] = original_role


@test("auto-update: skips when dev mode active")
def test_skips_when_dev_mode_active():
    """Test that check_for_updates skips when dev mode is active."""
    original_role = os.environ.get("INSTANCE_ROLE")
    try:
        os.environ["INSTANCE_ROLE"] = "production"
        with patch("infra.db.bot_state.get_dev_mode", return_value=True):
            import importlib
            import scripts.update
            importlib.reload(scripts.update)
            send_fn = AsyncMock()
            result = asyncio.run(scripts.update.check_for_updates(send_fn))
            assert result == "DONE: Skipped — dev mode active"
    finally:
        if original_role is None:
            os.environ.pop("INSTANCE_ROLE", None)
        else:
            os.environ["INSTANCE_ROLE"] = original_role


@test("auto-update: returns up-to-date when same commit")
def test_returns_uptodate_when_same_commit():
    """Test that check_for_updates returns up-to-date when local and remote match."""
    original_role = os.environ.get("INSTANCE_ROLE")
    try:
        os.environ["INSTANCE_ROLE"] = "production"
        with patch("infra.db.bot_state.get_dev_mode", return_value=False):
            with patch("subprocess.run") as mock_run:
                # Mock git fetch
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                # Mock local and remote commits (same)
                mock_run.side_effect = [
                    MagicMock(returncode=0, stdout="", stderr=""),  # fetch
                    MagicMock(returncode=0, stdout="abc1234\n", stderr=""),  # local
                    MagicMock(returncode=0, stdout="abc1234\n", stderr=""),  # remote
                ]
                import importlib
                import scripts.update
                importlib.reload(scripts.update)
                send_fn = AsyncMock()
                result = asyncio.run(scripts.update.check_for_updates(send_fn))
                assert "Already up to date" in result
                assert "abc1234" in result
    finally:
        if original_role is None:
            os.environ.pop("INSTANCE_ROLE", None)
        else:
            os.environ["INSTANCE_ROLE"] = original_role


@test("auto-update: triggers restart when behind")
def test_triggers_restart_when_behind():
    """Test that check_for_updates pulls and restarts when behind."""
    original_role = os.environ.get("INSTANCE_ROLE")
    try:
        os.environ["INSTANCE_ROLE"] = "production"
        with patch("infra.db.bot_state.get_dev_mode", return_value=False):
            with patch("subprocess.run") as mock_run:
                with patch("infra.db.autonomous.record_agent_action"):
                    # Mock git fetch, local (old), remote (new), pull success
                    mock_run.side_effect = [
                        MagicMock(returncode=0, stdout="", stderr=""),  # fetch
                        MagicMock(returncode=0, stdout="abc1234\n", stderr=""),  # local
                        MagicMock(returncode=0, stdout="def5678\n", stderr=""),  # remote
                        MagicMock(returncode=0, stdout="Fast-forward\n", stderr=""),  # pull
                    ]
                    with patch("subprocess.Popen") as mock_popen:
                        import importlib
                        import scripts.update
                        importlib.reload(scripts.update)
                        send_fn = AsyncMock()
                        result = asyncio.run(scripts.update.check_for_updates(send_fn))
                        assert "Restarting" in result
                        assert "def5678" in result
                        assert mock_popen.call_count == 2  # PrivyBot + PrivybotMCP
    finally:
        if original_role is None:
            os.environ.pop("INSTANCE_ROLE", None)
        else:
            os.environ["INSTANCE_ROLE"] = original_role


@test("auto-update: reports failure on pull error")
def test_reports_failure_on_pull_error():
    """Test that check_for_updates reports error when git pull fails."""
    original_role = os.environ.get("INSTANCE_ROLE")
    try:
        os.environ["INSTANCE_ROLE"] = "production"
        with patch("infra.db.bot_state.get_dev_mode", return_value=False):
            with patch("subprocess.run") as mock_run:
                # Mock git fetch, local (old), remote (new), pull failure
                mock_run.side_effect = [
                    MagicMock(returncode=0, stdout="", stderr=""),  # fetch
                    MagicMock(returncode=0, stdout="abc1234\n", stderr=""),  # local
                    MagicMock(returncode=0, stdout="def5678\n", stderr=""),  # remote
                    MagicMock(returncode=1, stdout="", stderr="Merge conflict\n"),  # pull fail
                ]
                import importlib
                import scripts.update
                importlib.reload(scripts.update)
                send_fn = AsyncMock()
                result = asyncio.run(scripts.update.check_for_updates(send_fn))
                assert "URGENT" in result
                assert "Auto-update failed" in result
    finally:
        if original_role is None:
            os.environ.pop("INSTANCE_ROLE", None)
        else:
            os.environ["INSTANCE_ROLE"] = original_role


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
