"""Tests for shell execution security model — ADR-039.

All tests mock subprocess.run. No real execution.
"""

import sys
import os
from unittest.mock import patch, MagicMock

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def _test_decorator(name):
    def wrapper(fn):
        fn.__name__ = name
        TESTS.append((name, fn))
        return fn
    return wrapper

test = _test_decorator

TESTS = []


@test("shell: allowed verb passes filter")
def test_allowed_verb_passes_filter():
    """'uv run pytest' → _check_command returns True."""
    from tools.system.shell import _check_command
    allowed, reason = _check_command("uv run pytest")
    assert allowed is True
    assert reason == "ok"


@test("shell: blocked verb fails filter")
def test_blocked_verb_fails_filter():
    """'rm -rf C:/' → returns False, reason contains 'verb'."""
    from tools.system.shell import _check_command
    allowed, reason = _check_command("rm -rf C:/")
    assert allowed is False
    assert "verb" in reason.lower()


@test("shell: blocked pattern fails filter")
def test_blocked_pattern_fails_filter():
    """'git status && del file.txt' → returns False, reason contains 'blocked pattern'."""
    from tools.system.shell import _check_command
    allowed, reason = _check_command("git status && del file.txt")
    assert allowed is False
    assert "blocked pattern" in reason.lower()


@test("shell: execute_shell blocked returns safe dict")
def test_execute_shell_blocked_returns_safe_dict():
    """Blocked command → {success: False, blocked: True}, subprocess never called."""
    from tools.system.shell import execute_shell
    with patch("tools.system.shell.subprocess.run") as mock_run:
        result = execute_shell("rm -rf C:/")
        assert result["success"] is False
        assert result["blocked"] is True
        assert "reason" in result
        assert mock_run.call_count == 0  # subprocess never called


@test("shell: named command resolves and executes")
def test_named_command_resolves_and_executes():
    """run_named_command('privy_tests') → mock called with correct command and cwd."""
    from tools.system.shell import run_named_command
    with patch("tools.system.shell.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = run_named_command("privy_tests")
        assert result["success"] is True
        assert result["command"] == "privy_tests"
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0]
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["shell"] is True
        assert call_kwargs["cwd"] == "C:/Github/PrivyBot"
        assert r".venv\Scripts\python.exe scripts\verify.py" in call_args[0]
        assert call_kwargs["timeout"] == 300


@test("shell: named command unknown returns available")
def test_named_command_unknown_returns_available():
    """run_named_command('__bad__') → error dict contains available list."""
    from tools.system.shell import run_named_command
    result = run_named_command("__bad__")
    assert result["success"] is False
    assert result["error"] == "unknown command"
    assert "available" in result
    assert isinstance(result["available"], list)
    assert len(result["available"]) > 0


@test("shell: execute_shell timeout handled")
def test_execute_shell_timeout_handled():
    """Mock raises TimeoutExpired → {success: False, error contains 'timeout'}."""
    from tools.system.shell import execute_shell
    from subprocess import TimeoutExpired
    with patch("tools.system.shell.subprocess.run", side_effect=TimeoutExpired("cmd", 30)):
        result = execute_shell("uv run pytest")
        assert result["success"] is False
        assert "timeout" in result["error"].lower()


@test("shell: list_named_commands returns all")
def test_list_named_commands_returns_all():
    """Returns dict with all 14 registered commands."""
    from tools.system.shell import list_named_commands
    result = list_named_commands()
    assert "commands" in result
    assert len(result["commands"]) == 14
    expected_commands = [
        "privy_tests", "list_services", "restart_privy", "restart_tailscale", "restart_mcp",
        "set_ollama_keepalive", "restart_ollama",
        "privy_status", "privy_pull", "privy_log", "tower_processes",
        "setup_profile_itch", "setup_profile_youtube", "check_profiles"
    ]
    for cmd in expected_commands:
        assert cmd in result["commands"]
        assert "command" in result["commands"][cmd]
        assert "description" in result["commands"][cmd]


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
