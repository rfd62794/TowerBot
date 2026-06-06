"""Tests for Playwright browser tools. All tests mock playwright.sync_api."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env")

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    passed = 0
    failed = 0

    for name, func in TESTS:
        try:
            func()
            print(f"  ✓ playwright: {name}")
            passed += 1
        except Exception as e:
            print(f"  ✗ playwright: {name}: {e}")
            failed += 1

    return passed, failed


@test("playwright: browser_navigate success")
def test_browser_navigate_success():
    """Mock playwright returns page with title/url → ok: True with url and title."""
    with patch("playwright.sync_api.sync_playwright") as mock_sync:
        # Setup mock chain
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.url = "https://example.com"
        mock_page.title.return_value = "Example Domain"
        mock_sync.return_value.__enter__.return_value = mock_playwright
        
        from tools.browser.playwright_base import browser_navigate
        result = browser_navigate("https://example.com")
        
        assert result["ok"] is True
        assert result["url"] == "https://example.com"
        assert result["title"] == "Example Domain"
        mock_browser.close.assert_called_once()


@test("playwright: browser_navigate no profile still works")
def test_browser_navigate_no_profile_still_works():
    """site=None → no profile loaded, still navigates."""
    with patch("playwright.sync_api.sync_playwright") as mock_sync:
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.url = "https://example.com"
        mock_page.title.return_value = "Example Domain"
        mock_sync.return_value.__enter__.return_value = mock_playwright
        
        from tools.browser.playwright_base import browser_navigate
        result = browser_navigate("https://example.com", site=None)
        
        assert result["ok"] is True
        # Should call new_context with empty dict or no args
        mock_browser.new_context.assert_called_once()


@test("playwright: browser_navigate failure")
def test_browser_navigate_failure():
    """Mock raises exception → ok: False with error."""
    with patch("playwright.sync_api.sync_playwright") as mock_sync:
        mock_sync.side_effect = Exception("Connection failed")
        
        from tools.browser.playwright_base import browser_navigate
        result = browser_navigate("https://example.com")
        
        assert result["ok"] is False
        assert "error" in result
        assert "Connection failed" in result["error"]


@test("playwright: get_profile missing")
def test_get_profile_missing():
    """No profile file exists → returns None, logs warning."""
    with patch("tools.browser.playwright_base.PROFILES_DIR", Path("/nonexistent")):
        with patch("tools.browser.playwright_base.logger") as mock_logger:
            from tools.browser.playwright_base import _get_profile
            result = _get_profile("test_site")
            
            assert result is None
            mock_logger.warning.assert_called_once()


@test("playwright: get_profile exists")
def test_get_profile_exists():
    """Profile JSON exists → returns dict with storage_state path."""
    with patch("tools.browser.playwright_base.PROFILES_DIR", Path("/fake")):
        with patch("pathlib.Path.exists", return_value=True):
            from tools.browser.playwright_base import _get_profile
            result = _get_profile("test_site")
            
            assert result is not None
            assert "storage_state" in result
            assert "test_site.json" in result["storage_state"]


@test("playwright: itch_post_devlog no profile")
def test_itch_post_devlog_no_profile():
    """No itch profile → ok: False with helpful error message."""
    with patch("tools.browser.itch_tools._get_profile", return_value=None):
        from tools.browser.itch_tools import itch_post_devlog
        result = itch_post_devlog(123, "Test Title", "Test Content")

        assert result["ok"] is False
        assert "error" in result
        assert "No itch.io profile" in result["error"]


@test("playwright: check_profile_validity no profile")
def test_check_profile_validity_no_profile():
    """No profile file → returns valid: False, reason: 'no profile file'."""
    with patch("tools.browser.playwright_base._get_profile", return_value=None):
        from tools.browser.playwright_base import check_profile_validity
        result = check_profile_validity("test_site")

        assert result["ok"] is True
        assert result["valid"] is False
        assert result["reason"] == "no profile file"
        assert result["site"] == "test_site"


@test("playwright: list_profile_status empty")
def test_list_profile_status_empty():
    """No profiles directory → returns empty list with message."""
    mock_dir = MagicMock()
    mock_dir.glob.return_value = []
    with patch("tools.browser.playwright_base.PROFILES_DIR", mock_dir):
        from tools.browser.playwright_base import list_profile_status
        result = list_profile_status()

        assert result["ok"] is True
        assert result["profiles"] == []
        assert "message" in result
        assert "No profiles found" in result["message"]


@test("playwright: check_profile_validity handles exception")
def test_check_profile_validity_handles_exception():
    """Mock playwright raises → returns ok: False, valid: False."""
    with patch("tools.browser.playwright_base._get_profile", return_value={"storage_state": "fake.json"}):
        with patch("playwright.sync_api.sync_playwright") as mock_sync:
            mock_playwright = MagicMock()
            mock_playwright.chromium.launch.side_effect = Exception("Playwright error")
            mock_sync.return_value.__enter__.return_value = mock_playwright

            from tools.browser.playwright_base import check_profile_validity
            result = check_profile_validity("test_site")

            assert result["ok"] is False
            assert result["valid"] is False
            assert "error" in result or "reason" in result


if __name__ == "__main__":
    passed, failed = run_all()
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
