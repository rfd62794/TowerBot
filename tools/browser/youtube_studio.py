"""YouTube Studio browser automation — for actions not available via API."""
import logging
from tools.browser.playwright_base import _get_profile

logger = logging.getLogger("privy.browser.youtube")

STUDIO_SITE = "youtube_studio"


def pin_youtube_comment(video_id: str, comment_id: str) -> dict:
    """
    Pin a comment on a YouTube video via YouTube Studio.
    Requires youtube_studio profile — run setup_profile('youtube_studio') first.
    Returns: {ok, video_id, comment_id}
    """
    try:
        from playwright.sync_api import sync_playwright
        profile = _get_profile(STUDIO_SITE)
        if not profile:
            return {"ok": False, "error": "No YouTube Studio profile. Run setup_profile('youtube_studio') first."}

        url = f"https://studio.youtube.com/video/{video_id}/comments"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(**profile)
            page = context.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle")
            # Click the three-dot menu on the target comment and select Pin
            comment_selector = f'[data-comment-id="{comment_id}"]'
            page.locator(comment_selector).hover()
            page.locator(f'{comment_selector} button[aria-label="More actions"]').click()
            page.get_by_text("Pin comment").click()
            page.wait_for_load_state("networkidle")
            browser.close()
            return {"ok": True, "video_id": video_id, "comment_id": comment_id, "pinned": True}
    except Exception as e:
        logger.error(f"[youtube] pin comment failed: {e}")
        return {"ok": False, "error": str(e)}
