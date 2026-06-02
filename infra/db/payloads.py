"""
Payload CRUD operations.
JSON serialization lives here. Schema validation is a Phase 21 concern.
"""
import json
import uuid
import logging
from datetime import datetime, timezone
from infra.db.schema import _exec

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


def create_payload(chain_id: str, payload_type: str, data: dict,
                   step_id: str = None,
                   schema_version: str = 'v1') -> dict:
    """Create and persist a payload. data must be a dict."""
    if not isinstance(data, dict):
        raise TypeError(f"data must be a dict, got {type(data).__name__}")
    
    # Validate with Pydantic — adds chain_id and schema_version
    try:
        from infra.chain.schemas import validate_payload
        validated = validate_payload(payload_type, {
            **data,
            "chain_id": chain_id,
            "step_id": step_id,
            "schema_version": schema_version
        })
        serialized = validated.to_db_dict()
    except Exception as e:
        # Log the error and fall back to raw dict — never crash a chain
        logger.warning(f"Pydantic validation failed for payload_type '{payload_type}': {e}. Falling back to raw dict.")
        serialized = {
            **data,
            "chain_id": chain_id,
            "step_id": step_id,
            "schema_version": schema_version
        }
    
    payload_id = _uuid()
    now = _now()
    _exec(
        """INSERT INTO chain_payloads
           (id, chain_id, step_id, type, schema_version, data, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (payload_id, chain_id, step_id, payload_type,
         schema_version, json.dumps(serialized), now),
        commit=True,
    )
    return get_payload(payload_id)


def get_payload(payload_id: str) -> dict | None:
    """Fetch a payload by ID. Deserializes data field from JSON."""
    row = _exec(
        "SELECT * FROM chain_payloads WHERE id=?", (payload_id,)
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result['data'] = json.loads(result['data'])
    return result


def list_payloads_for_chain(chain_id: str) -> list[dict]:
    """Return all payloads for a chain ordered by created_at."""
    rows = _exec(
        """SELECT * FROM chain_payloads WHERE chain_id=?
           ORDER BY created_at ASC""",
        (chain_id,),
    ).fetchall()
    result = []
    for row in rows:
        r = dict(row)
        r['data'] = json.loads(r['data'])
        result.append(r)
    return result
