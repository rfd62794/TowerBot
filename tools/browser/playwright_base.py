"""Core Playwright browser tools. All tools use saved storageState profiles."""
import os
import logging
from pathlib import Path

logger = logging.getLogger("privy.browser")

PROFILES_DIR = Path("config/playwright_profiles")


def _get_profile(site: str) -> dict | None:
    """Load storageState for a site. Returns None if not found."""
    profile_path = PROFILES_DIR / f"{site}.json"
    if not profile_path.exists():
        logger.warning(f"[browser] no profile for {site} — run setup_profile('{site}') first")
        return None
    return {"storage_state": str(profile_path)}


def browser_navigate(url: str, site: str = None) -> dict:
    """Navigate to URL and return page title and current URL."""
    try:
        from playwright.sync_api import sync_playwright
        profile = _get_profile(site) if site else {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(**(profile or {}))
            page = context.new_page()
            page.goto(url, timeout=30000)
            result = {"ok": True, "url": page.url, "title": page.title()}
            browser.close()
            return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


def browser_get_text(url: str, selector: str, site: str = None) -> dict:
    """Get text content of an element."""
    try:
        from playwright.sync_api import sync_playwright
        profile = _get_profile(site) if site else {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(**(profile or {}))
            page = context.new_page()
            page.goto(url, timeout=30000)
            element = page.locator(selector).first
            text = element.inner_text()
            browser.close()
            return {"ok": True, "text": text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def browser_screenshot(url: str, site: str = None) -> dict:
    """Navigate to URL and return base64 screenshot."""
    try:
        import base64
        from playwright.sync_api import sync_playwright
        profile = _get_profile(site) if site else {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(**(profile or {}))
            page = context.new_page()
            page.goto(url, timeout=30000)
            img_bytes = page.screenshot()
            browser.close()
            return {"ok": True, "screenshot_b64": base64.b64encode(img_bytes).decode()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def setup_profile(site: str) -> dict:
    """
    Launch headed browser for manual login. Saves storageState on close.
    Run this interactively — not via autonomous tasks.
    """
    try:
        from playwright.sync_api import sync_playwright
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        profile_path = PROFILES_DIR / f"{site}.json"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            page.goto("https://www.google.com")
            input(f"Log into {site} manually, then press Enter to save session...")
            context.storage_state(path=str(profile_path))
            browser.close()
        return {"ok": True, "profile_saved": str(profile_path)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
