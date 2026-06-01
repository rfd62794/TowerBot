"""Tests for auto-update system."""

import sys
import os
import subprocess
from unittest.mock import patch, MagicMock

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


@test("auto-update: trigger_restart spawns two processes")
def test_trigger_restart_spawns_two_processes():
    """Mock subprocess.Popen. Assert it is called exactly twice after a successful pull."""
    from scripts.update import trigger_restart
    with patch("subprocess.Popen") as mock_popen:
        trigger_restart()
        assert mock_popen.call_count == 2


@test("auto-update: mcp restart delay longer than bot")
def test_mcp_restart_delay_longer_than_bot():
    """Assert the PrivybotMCP PowerShell command contains Start-Sleep -Seconds 5 (or greater) and PrivyBot contains a shorter delay."""
    from scripts.update import trigger_restart
    with patch("subprocess.Popen") as mock_popen:
        trigger_restart()
        
        # Get the command strings from the two calls
        calls = mock_popen.call_args_list
        bot_cmd = str(calls[0])
        mcp_cmd = str(calls[1])
        
        # PrivyBot should have shorter delay (2 seconds)
        assert "Start-Sleep -Seconds 2" in bot_cmd or "Start-Sleep 2" in bot_cmd
        # PrivybotMCP should have longer delay (5 seconds or more)
        assert "Start-Sleep -Seconds 5" in mcp_cmd or "Start-Sleep 5" in mcp_cmd


@test("auto-update: trigger_restart detached")
def test_trigger_restart_detached():
    """Assert both Popen calls use DETACHED_PROCESS flag."""
    from scripts.update import trigger_restart
    with patch("subprocess.Popen") as mock_popen:
        trigger_restart()
        
        calls = mock_popen.call_args_list
        for call in calls:
            kwargs = call[1] if call[1] else {}
            creationflags = kwargs.get('creationflags', 0)
            assert creationflags & subprocess.DETACHED_PROCESS


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
