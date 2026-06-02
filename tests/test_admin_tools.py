"""Tests for admin diagnostic tools — get_logs and run_diagnostic.

All tests use mocks. No real log file reads, subprocess calls, or DB access.
"""
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import pytest
from unittest.mock import patch, MagicMock, mock_open


# --- get_logs tests ---

def test_get_logs_returns_lines():
    """Mock file read returning 10 lines — ok=True, total_lines=10."""
    from tools.meta.admin import get_logs
    mock_lines = [f"line {i}\n" for i in range(10)]
    with patch("builtins.open", mock_open(read_data="".join(mock_lines))):
        with patch("os.path.exists", return_value=True):
            result = get_logs(lines=10)
            assert result["ok"] is True
            assert result["total_lines"] == 10


def test_get_logs_filter():
    """Mock file with mixed lines — filter_str='ERROR' returns only matching."""
    from tools.meta.admin import get_logs
    mock_lines = "INFO: normal\nERROR: bad thing\nINFO: ok\n"
    with patch("builtins.open", mock_open(read_data=mock_lines)):
        with patch("os.path.exists", return_value=True):
            result = get_logs(lines=10, filter_str="ERROR")
            assert result["ok"] is True
            assert result["filtered"] is True
            assert len(result["lines"]) == 1
            assert "ERROR" in result["lines"][0]


def test_get_logs_caps_at_200():
    """lines=500 passed — capped to 200 in request."""
    from tools.meta.admin import get_logs
    mock_lines = "".join([f"line {i}\n" for i in range(500)])
    with patch("builtins.open", mock_open(read_data=mock_lines)):
        with patch("os.path.exists", return_value=True):
            result = get_logs(lines=500)
            assert result["ok"] is True
            # Should cap at 200
            assert len(result["lines"]) == 200


def test_get_logs_file_not_found():
    """Log path doesn't exist — ok=False, error present."""
    from tools.meta.admin import get_logs
    with patch("os.path.exists", return_value=False):
        result = get_logs()
        assert result["ok"] is False
        assert "error" in result
        assert "not found" in result["error"]


def test_get_logs_encoding_error():
    """File with bad bytes — ok=True, errors replaced not crashed."""
    from tools.meta.admin import get_logs
    # Simulate encoding error by raising UnicodeDecodeError
    with patch("builtins.open", side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "")):
        with patch("os.path.exists", return_value=True):
            result = get_logs()
            assert result["ok"] is False
            assert "error" in result


# --- run_diagnostic tests ---

def test_run_diagnostic_returns_ok():
    """All sections succeed — ok=True, all keys present."""
    from tools.meta.admin import run_diagnostic
    with patch("subprocess.run", return_value=MagicMock(stdout="abc1234", returncode=0)):
        with patch("tools.meta.admin.get_logs", return_value={"ok": True, "lines": []}):
            with patch("infra.db.schema._exec", return_value=[{"c": 5}]):
                with patch("infra.memory_manager.memory_manager", MagicMock(collection=MagicMock())):
                    result = run_diagnostic()
                    assert result["ok"] is True
                    assert "git_head" in result
                    assert "queue_depth" in result
                    assert "null_task_count" in result
                    assert "memory_count" in result
                    assert "chroma_status" in result
                    assert "recent_errors" in result
                    assert "last_failed_tasks" in result


def test_run_diagnostic_partial_failure():
    """DB unavailable — ok=True, queue_depth=-1, no crash."""
    from tools.meta.admin import run_diagnostic
    with patch("subprocess.run", return_value=MagicMock(stdout="abc1234", returncode=0)):
        with patch("tools.meta.admin.get_logs", return_value={"ok": True, "lines": []}):
            with patch("infra.db.schema._exec", side_effect=Exception("DB gone")):
                with patch("infra.memory_manager.memory_manager", MagicMock(collection=MagicMock())):
                    result = run_diagnostic()
                    assert result["ok"] is True
                    assert result["queue_depth"] == -1
                    assert result["null_task_count"] == -1
                    assert result["memory_count"] == -1


# --- registry test ---

def test_get_logs_and_run_diagnostic_in_registry():
    """Assert both names present in TOOL_REGISTRY keys."""
    from tools.registry import TOOL_REGISTRY
    assert "get_logs" in TOOL_REGISTRY
    assert "run_diagnostic" in TOOL_REGISTRY


# --- run_all shim for verify.py ---

TESTS = [
    ("get_logs_returns_lines", test_get_logs_returns_lines),
    ("get_logs_filter", test_get_logs_filter),
    ("get_logs_caps_at_200", test_get_logs_caps_at_200),
    ("get_logs_file_not_found", test_get_logs_file_not_found),
    ("get_logs_encoding_error", test_get_logs_encoding_error),
    ("run_diagnostic_returns_ok", test_run_diagnostic_returns_ok),
    ("run_diagnostic_partial_failure", test_run_diagnostic_partial_failure),
    ("get_logs_and_run_diagnostic_in_registry", test_get_logs_and_run_diagnostic_in_registry),
]


def run_all() -> tuple[int, int]:
    passed = failed = 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"  \u2713 admin_tools: {name}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 admin_tools: {name}: {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
