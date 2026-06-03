"""
Goals and milestones CRUD operations.
Separated from deprecated tasks table per ADR-038 Phase 2.
"""
from infra.db.schema import _exec


def upsert_goal(goal_id: str, title: str, description: str = None,
                deadline: str = None, status: str = "active") -> None:
    """Insert or update a goal."""
    _exec(
        """INSERT OR REPLACE INTO goals (id, title, description, deadline, status)
           VALUES (?, ?, ?, ?, ?)""",
        (goal_id, title, description, deadline, status),
        commit=True,
    )


def get_goals(status: str = None) -> list[dict]:
    """Get all goals, optionally filtered by status."""
    if status:
        rows = _exec(
            "SELECT * FROM goals WHERE status=? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    else:
        rows = _exec(
            "SELECT * FROM goals ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_goal(goal_id: str) -> dict | None:
    """Get a single goal by ID."""
    row = _exec(
        "SELECT * FROM goals WHERE id=?",
        (goal_id,),
    ).fetchone()
    return dict(row) if row else None


def upsert_milestone(milestone_id: str, goal_id: str, title: str,
                     deadline: str = None, status: str = "not_started",
                     notes: str = None) -> None:
    """Insert or update a milestone."""
    _exec(
        """INSERT OR REPLACE INTO milestones (id, goal_id, title, deadline, status, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (milestone_id, goal_id, title, deadline, status, notes),
        commit=True,
    )


def get_milestones(goal_id: str = None) -> list[dict]:
    """Get milestones, optionally filtered by goal_id."""
    if goal_id:
        rows = _exec(
            "SELECT * FROM milestones WHERE goal_id=? ORDER BY deadline",
            (goal_id,),
        ).fetchall()
    else:
        rows = _exec(
            "SELECT * FROM milestones ORDER BY deadline"
        ).fetchall()
    return [dict(r) for r in rows]


def get_milestone(milestone_id: str) -> dict | None:
    """Get a single milestone by ID."""
    row = _exec(
        "SELECT * FROM milestones WHERE id=?",
        (milestone_id,),
    ).fetchone()
    return dict(row) if row else None
