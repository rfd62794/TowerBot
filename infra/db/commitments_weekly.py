"""
Commitments and weekly plans CRUD operations.
Separated from deprecated tasks table per ADR-038 Phase 2.
"""
from infra.db.schema import _exec


def add_commitment(description: str, deadline: str = None) -> int:
    """Add a commitment. Returns the commitment ID."""
    _exec(
        "INSERT INTO commitments (description, deadline, status) VALUES (?, ?, 'pending')",
        (description, deadline),
        commit=True,
    )
    row = _exec("SELECT last_insert_rowid()").fetchone()
    return row[0]


def list_commitments(status: str = None) -> list[dict]:
    """List commitments, optionally filtered by status."""
    if status:
        rows = _exec(
            "SELECT * FROM commitments WHERE status=? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    else:
        rows = _exec(
            "SELECT * FROM commitments ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_weekly_plan(week_start: str, week_end: str, focus: str = None,
                       notes: str = None) -> None:
    """Insert or update a weekly plan."""
    _exec(
        """INSERT OR REPLACE INTO weekly_plans (week_start, week_end, focus, notes)
           VALUES (?, ?, ?, ?)""",
        (week_start, week_end, focus, notes),
        commit=True,
    )


def get_current_weekly_plan() -> dict | None:
    """Get the current weekly plan (most recent by week_start)."""
    row = _exec(
        "SELECT * FROM weekly_plans ORDER BY week_start DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None
