"""Content deduplication helpers — track what's been served to avoid repeats."""
import logging
from infra.db.schema import _exec

logger = logging.getLogger("privy.content")


def already_served(source: str, external_id: str) -> bool:
    """Returns True if this item was already sent to Telegram."""
    try:
        rows = _exec(
            "SELECT served FROM content_seen WHERE source=? AND external_id=?",
            (source, str(external_id))
        )
        if not rows:
            return False
        return bool(rows[0]["served"])
    except Exception as e:
        logger.warning(f"[content_seen] already_served failed: {e}")
        return False


def mark_served(source: str, external_id: str, title: str = "", url: str = "") -> None:
    """Upsert to content_seen with served=1."""
    try:
        _exec(
            """INSERT INTO content_seen (source, external_id, title, url, served)
               VALUES (?, ?, ?, ?, 1)
               ON CONFLICT(source, external_id) DO UPDATE SET served=1""",
            (source, str(external_id), title or "", url or "")
        )
        logger.debug(f"[content_seen] marked served: {source}/{external_id}")
    except Exception as e:
        logger.warning(f"[content_seen] mark_served failed: {e}")
