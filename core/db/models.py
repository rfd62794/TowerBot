"""Model status / throttle tracking."""

from core.db.schema import _exec


def record_throttle(model_id: str, retry_after: float) -> None:
    _exec(
        "INSERT INTO model_status "
        "(model_id, last_429, retry_after_seconds, fail_count, last_checked) "
        "VALUES (?, CURRENT_TIMESTAMP, ?, 1, CURRENT_TIMESTAMP) "
        "ON CONFLICT(model_id) DO UPDATE SET "
        "last_429 = CURRENT_TIMESTAMP, "
        "retry_after_seconds = excluded.retry_after_seconds, "
        "fail_count = model_status.fail_count + 1, "
        "last_checked = CURRENT_TIMESTAMP",
        (model_id, retry_after), commit=True,
    )


def record_success(model_id: str) -> None:
    _exec(
        "INSERT INTO model_status "
        "(model_id, last_success, fail_count, last_429, last_checked) "
        "VALUES (?, CURRENT_TIMESTAMP, 0, NULL, CURRENT_TIMESTAMP) "
        "ON CONFLICT(model_id) DO UPDATE SET "
        "last_success = CURRENT_TIMESTAMP, "
        "fail_count = 0, last_429 = NULL, last_checked = CURRENT_TIMESTAMP",
        (model_id,), commit=True,
    )


def get_throttled_models() -> list[str]:
    rows = _exec(
        "SELECT model_id FROM model_status WHERE last_429 IS NOT NULL "
        "AND datetime(last_429, '+' || retry_after_seconds || ' seconds') "
        "> datetime('now')"
    ).fetchall()
    return [r["model_id"] for r in rows]


def get_model_status_all() -> list[dict]:
    rows = _exec(
        "SELECT model_id, last_429, retry_after_seconds, fail_count, last_success "
        "FROM model_status ORDER BY model_id"
    ).fetchall()
    return [dict(r) for r in rows]
