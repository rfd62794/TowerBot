"""
Pattern observer — watches completed chains for reuse patterns.
Writes to pattern_candidates table when a sequence repeats.
Runs as an APScheduler job.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from infra.db.schema import _exec
from infra.db.chains import get_steps_for_chain, list_chains

logger = logging.getLogger(__name__)

PROMOTION_THRESHOLD = 3      # observations before candidate flagged
SUCCESS_RATE_FLOOR = 0.7     # minimum success rate to promote


def _sequence_hash(steps: list[dict]) -> str:
    """Hash a step sequence by type and name for pattern matching."""
    sequence = [(s["step_type"], s["name"]) for s in steps]
    serialized = json.dumps(sequence, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def observe_completed_chains() -> dict:
    """
    Main observer job. Call this from APScheduler.
    Scans recently completed chains, extracts step sequences,
    updates pattern_candidates table.
    Returns summary dict.
    """
    completed = list_chains(status="complete")
    candidates_updated = 0
    candidates_new = 0

    for chain in completed:
        steps = get_steps_for_chain(chain["id"])
        if not steps:
            continue

        seq_hash = _sequence_hash(steps)
        total = len(steps)
        successful = sum(1 for s in steps if s["status"] == "complete")
        success_rate = successful / total if total > 0 else 0.0

        existing = _exec(
            "SELECT * FROM pattern_candidates WHERE step_sequence_hash=?",
            (seq_hash,)
        ).fetchone()

        if existing:
            row = dict(existing)
            new_count = row["observed_count"] + 1
            new_rate = (
                (row["success_rate"] * row["observed_count"] + success_rate)
                / new_count
            )
            status = row["promotion_status"]
            if (new_count >= PROMOTION_THRESHOLD and
                    new_rate >= SUCCESS_RATE_FLOOR and
                    status == "candidate"):
                status = "ready_to_promote"

            _exec(
                """UPDATE pattern_candidates
                   SET observed_count=?, last_seen=?, success_rate=?,
                       promotion_status=?
                   WHERE step_sequence_hash=?""",
                (new_count, _now(), new_rate, status, seq_hash),
                commit=True
            )
            candidates_updated += 1

        else:
            import uuid
            _exec(
                """INSERT INTO pattern_candidates
                   (id, step_sequence_hash, observed_count,
                    first_seen, last_seen, success_rate,
                    promotion_status)
                   VALUES (?, ?, 1, ?, ?, ?, 'candidate')""",
                (str(uuid.uuid4()), seq_hash, _now(), _now(),
                 success_rate),
                commit=True
            )
            candidates_new += 1

    logger.info(
        f"Observer run: {candidates_new} new, "
        f"{candidates_updated} updated patterns"
    )
    return {
        "chains_scanned": len(completed),
        "candidates_new": candidates_new,
        "candidates_updated": candidates_updated
    }


def get_promotion_candidates() -> list[dict]:
    """Return all pattern candidates ready to promote."""
    rows = _exec(
        """SELECT * FROM pattern_candidates
           WHERE promotion_status='ready_to_promote'
           ORDER BY observed_count DESC"""
    )
    return [dict(r) for r in rows] if rows else []
