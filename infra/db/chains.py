"""
Chain and step CRUD operations.
No business logic. No runner. Data access only.
"""
import uuid
from datetime import datetime, timezone
from infra.db.schema import _exec


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


# --- Chains ---

def create_chain(template_name: str, payload_ref: str = None) -> dict:
    """Create a new chain. Returns the created chain dict."""
    chain_id = _uuid()
    now = _now()
    _exec(
        """INSERT INTO chains
           (id, template_name, status, current_step, payload_ref,
            created_at, updated_at)
           VALUES (?, ?, 'running', 0, ?, ?, ?)""",
        (chain_id, template_name, payload_ref, now, now),
        commit=True,
    )
    return get_chain(chain_id)


def get_chain(chain_id: str) -> dict | None:
    """Fetch a chain by ID. Returns dict or None."""
    row = _exec(
        "SELECT * FROM chains WHERE id = ?", (chain_id,)
    ).fetchone()
    return dict(row) if row else None


def update_chain_status(chain_id: str, status: str,
                        current_step: int = None) -> None:
    """Update chain status and optionally current_step."""
    now = _now()
    completed_at = now if status in ('complete', 'failed') else None
    if current_step is not None:
        _exec(
            """UPDATE chains SET status=?, current_step=?,
               updated_at=?, completed_at=?
               WHERE id=?""",
            (status, current_step, now, completed_at, chain_id),
            commit=True,
        )
    else:
        _exec(
            """UPDATE chains SET status=?, updated_at=?,
               completed_at=? WHERE id=?""",
            (status, now, completed_at, chain_id),
            commit=True,
        )


def list_chains(status: str = None) -> list[dict]:
    """List chains, optionally filtered by status."""
    if status:
        rows = _exec(
            "SELECT * FROM chains WHERE status=? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    else:
        rows = _exec(
            "SELECT * FROM chains ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# --- Steps ---

def append_step(chain_id: str, step_index: int, step_type: str,
                name: str) -> dict:
    """Append a step to a chain. Returns the created step dict."""
    step_id = _uuid()
    _exec(
        """INSERT INTO chain_steps
           (id, chain_id, step_index, step_type, name, status)
           VALUES (?, ?, ?, ?, ?, 'pending')""",
        (step_id, chain_id, step_index, step_type, name),
        commit=True,
    )
    return get_step(step_id)


def get_step(step_id: str) -> dict | None:
    """Fetch a step by ID."""
    row = _exec(
        "SELECT * FROM chain_steps WHERE id=?", (step_id,)
    ).fetchone()
    return dict(row) if row else None


def update_step(step_id: str, status: str,
                input_payload_id: str = None,
                output_payload_id: str = None,
                error: str = None) -> None:
    """Update step status and payload references."""
    now = _now()
    started_at = now if status == 'running' else None
    completed_at = now if status in ('complete', 'failed') else None
    _exec(
        """UPDATE chain_steps SET status=?, input_payload_id=?,
           output_payload_id=?, started_at=COALESCE(started_at, ?),
           completed_at=?, error=? WHERE id=?""",
        (status, input_payload_id, output_payload_id,
         started_at, completed_at, error, step_id),
        commit=True,
    )


def get_steps_for_chain(chain_id: str) -> list[dict]:
    """Return all steps for a chain ordered by step_index."""
    rows = _exec(
        """SELECT * FROM chain_steps WHERE chain_id=?
           ORDER BY step_index ASC""",
        (chain_id,),
    ).fetchall()
    return [dict(r) for r in rows]
