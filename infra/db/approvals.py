"""Approval gate CRUD — simple YES/NO actions for autonomous tasks."""
import json
import logging
from datetime import datetime, timedelta
from infra.db.schema import _exec

logger = logging.getLogger("privy.approvals")


def create_approval(action_type: str, summary: str, payload: dict,
                    timeout_minutes: int = 30) -> int | None:
    """Create pending approval. Returns approval ID."""
    try:
        expires_at = (datetime.utcnow() + timedelta(minutes=timeout_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        cur = _exec(
            "INSERT INTO action_approvals (action_type, summary, payload, expires_at) "
            "VALUES (?, ?, ?, ?) RETURNING id",
            (action_type, summary, json.dumps(payload), expires_at)
        )
        row = cur.fetchone()
        return row["id"] if row else None
    except Exception as e:
        logger.warning(f"[approvals] create_approval failed: {e}")
        return None


def get_pending_approval(approval_id: int) -> dict | None:
    """Get a pending approval by ID."""
    try:
        rows = _exec(
            "SELECT * FROM action_approvals WHERE id=? AND status='pending'",
            (approval_id,)
        )
        return dict(rows[0]) if rows else None
    except Exception as e:
        logger.warning(f"[approvals] get_pending_approval failed: {e}")
        return None


def resolve_approval(approval_id: int, status: str) -> None:
    """Resolve approval as 'approved' or 'rejected'."""
    try:
        resolved_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        _exec(
            "UPDATE action_approvals SET status=?, resolved_at=? WHERE id=?",
            (status, resolved_at, approval_id),
            commit=True
        )
    except Exception as e:
        logger.warning(f"[approvals] resolve_approval failed: {e}")


def expire_stale_approvals() -> int:
    """Mark expired pending approvals. Returns count expired."""
    try:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cur = _exec(
            "UPDATE action_approvals SET status='expired' "
            "WHERE status='pending' AND expires_at < ? RETURNING id",
            (now,),
            commit=True
        )
        rows = cur.fetchall()
        return len(rows) if rows else 0
    except Exception as e:
        logger.warning(f"[approvals] expire_stale_approvals failed: {e}")
        return 0


def get_latest_pending() -> dict | None:
    """Get the most recent pending approval, if any."""
    try:
        cur = _exec(
            "SELECT * FROM action_approvals WHERE status='pending' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.warning(f"[approvals] get_latest_pending failed: {e}")
        return None
