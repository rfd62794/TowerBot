"""itch.io browser automation tools."""
import logging
from tools.browser.playwright_base import _get_profile

logger = logging.getLogger("privy.browser.itch")

ITCH_SITE = "itch"
DEVLOG_URL = "https://itch.io/dashboard/game/{game_id}/edit/devlog/new"


def itch_post_devlog(game_id: int, title: str, content: str) -> dict:
    """
    Post a devlog on itch.io for a game.
    Requires itch profile — run setup_profile('itch') first.
    Returns: {ok, url, title}
    """
    try:
        from playwright.sync_api import sync_playwright
        profile = _get_profile(ITCH_SITE)
        if not profile:
            return {"ok": False, "error": "No itch.io profile. Run setup_profile('itch') first."}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(**profile)
            page = context.new_page()
            page.goto(DEVLOG_URL.format(game_id=game_id), timeout=30000)
            page.fill('input[name="title"]', title)
            page.fill('textarea[name="body"]', content)
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")
            result_url = page.url
            browser.close()
            return {"ok": True, "url": result_url, "title": title}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def itch_get_game_page(game_id: int) -> dict:
    """Get text content of a game's itch.io page."""
    try:
        from playwright.sync_api import sync_playwright
        profile = _get_profile(ITCH_SITE)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(**(profile or {}))
            page = context.new_page()
            page.goto(f"https://rdug627.itch.io/voidrift", timeout=30000)
            text = page.locator(".game_description").first.inner_text()
            browser.close()
            return {"ok": True, "description": text}
    except Exception as e:
        return {"ok": False, "error": str(e)}
