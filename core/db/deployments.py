"""Deploy history — tracks deploy attempts, verify results, and stable commits."""

from core.db.schema import _exec


def record_deploy(commit_hash: str, commit_message: str) -> int:
    """Record a new deploy attempt. Returns the row id."""
    cur = _exec(
        "INSERT INTO deploy_history (commit_hash, commit_message) VALUES (?, ?)",
        (commit_hash, commit_message),
        commit=True,
    )
    return cur.lastrowid


def mark_verify_passed(deploy_id: int) -> None:
    """Mark a deploy record as having passed verify."""
    _exec(
        "UPDATE deploy_history SET verify_passed = 1 WHERE id = ?",
        (deploy_id,),
        commit=True,
    )


def mark_stable(deploy_id: int) -> None:
    """Mark a deploy record as stable (verify passed + service restarted)."""
    _exec(
        "UPDATE deploy_history SET stable = 1 WHERE id = ?",
        (deploy_id,),
        commit=True,
    )


def mark_rolled_back(deploy_id: int) -> None:
    """Mark a deploy record as rolled back."""
    _exec(
        "UPDATE deploy_history SET rolled_back = 1 WHERE id = ?",
        (deploy_id,),
        commit=True,
    )


def get_last_stable_commit() -> dict | None:
    """Return the most recent deploy record where stable=1, or None."""
    cur = _exec(
        "SELECT * FROM deploy_history WHERE stable = 1 ORDER BY deployed_at DESC, id DESC LIMIT 1"
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_last_deploy() -> dict | None:
    """Return the most recent deploy record regardless of status, or None."""
    cur = _exec(
        "SELECT * FROM deploy_history ORDER BY deployed_at DESC, id DESC LIMIT 1"
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_deploy_history(limit: int = 10) -> list[dict]:
    """Return the last N deploy records, newest first."""
    cur = _exec(
        "SELECT * FROM deploy_history ORDER BY deployed_at DESC LIMIT ?",
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]
