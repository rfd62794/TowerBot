"""Content deduplication for autonomous task outputs."""
from datetime import datetime
from infra.db.schema import _exec


def already_served(source: str, external_id: str) -> bool:
    """Returns True if this item was already sent to Telegram."""
    row = _exec(
        "SELECT served FROM content_seen WHERE source = ? AND external_id = ?",
        (source, external_id)
    ).fetchone()
    return row is not None and row["served"] == 1


def mark_served(source: str, external_id: str, title: str, url: str) -> None:
    """Upsert to content_seen with served=1."""
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _exec(
        """INSERT INTO content_seen (source, external_id, title, url, seen_at, served)
           VALUES (?, ?, ?, ?, ?, 1)
           ON CONFLICT(source, external_id) DO UPDATE SET
           served = 1, seen_at = ?""",
        (source, external_id, title, url, now, now),
        commit=True
    )
