"""Goals, milestones, tasks, and weekly plans CRUD."""

from datetime import datetime
from core.db.schema import _exec


def upsert_goal(goal_id: str, title: str, description: str, deadline: str,
                status: str = "active", progress_pct: int = 0, notes: str = None) -> None:
    _exec(
        "INSERT OR REPLACE INTO goals (id, title, description, deadline, status, progress_pct, notes, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (goal_id, title, description, deadline, status, progress_pct, notes), commit=True,
    )


def get_goals(status: str = None) -> list[dict]:
    if status:
        rows = _exec(
            "SELECT * FROM goals WHERE status = ? ORDER BY deadline ASC",
            (status,),
        ).fetchall()
    else:
        rows = _exec("SELECT * FROM goals ORDER BY deadline ASC").fetchall()
    return [dict(r) for r in rows]


def get_goal(goal_id: str) -> dict | None:
    row = _exec("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    return dict(row) if row else None


def upsert_milestone(milestone_id: str, goal_id: str, title: str, deadline: str,
                     status: str = "not_started", notes: str = None) -> None:
    _exec(
        "INSERT OR REPLACE INTO milestones (id, goal_id, title, deadline, status, notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (milestone_id, goal_id, title, deadline, status, notes), commit=True,
    )


def get_milestones(goal_id: str = None) -> list[dict]:
    if goal_id:
        rows = _exec(
            "SELECT * FROM milestones WHERE goal_id = ? ORDER BY deadline ASC",
            (goal_id,),
        ).fetchall()
    else:
        rows = _exec("SELECT * FROM milestones ORDER BY deadline ASC").fetchall()
    return [dict(r) for r in rows]


def get_milestone(milestone_id: str) -> dict | None:
    row = _exec("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
    return dict(row) if row else None


def upsert_task(task_id: str, title: str, due_date: str, milestone_id: str = None,
                scheduled_at: str = None, status: str = "pending", recurrence: str = None,
                reminder_minutes: int = 60) -> None:
    _exec(
        "INSERT OR REPLACE INTO tasks (id, milestone_id, title, due_date, scheduled_at, status, recurrence, reminder_minutes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, milestone_id, title, due_date, scheduled_at, status, recurrence, reminder_minutes), commit=True,
    )


def get_tasks(status: str = None, due_date: str = None) -> list[dict]:
    if status and due_date:
        rows = _exec(
            "SELECT * FROM tasks WHERE status = ? AND due_date = ? ORDER BY due_date ASC",
            (status, due_date),
        ).fetchall()
    elif status:
        rows = _exec(
            "SELECT * FROM tasks WHERE status = ? ORDER BY due_date ASC",
            (status,),
        ).fetchall()
    elif due_date:
        rows = _exec(
            "SELECT * FROM tasks WHERE due_date = ? ORDER BY due_date ASC",
            (due_date,),
        ).fetchall()
    else:
        rows = _exec("SELECT * FROM tasks ORDER BY due_date ASC").fetchall()
    return [dict(r) for r in rows]


def get_task(task_id: str) -> dict | None:
    row = _exec("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def update_task_status(task_id: str, status: str) -> None:
    completed_at = "CURRENT_TIMESTAMP" if status == "complete" else "NULL"
    _exec(
        f"UPDATE tasks SET status = ?, completed_at = {completed_at} WHERE id = ?",
        (status, task_id), commit=True,
    )


def get_tasks_due_today() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    rows = _exec(
        "SELECT * FROM tasks WHERE due_date = ? AND status != 'complete' ORDER BY scheduled_at ASC",
        (today,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_upcoming_scheduled(hours: int = 24) -> list[dict]:
    rows = _exec(
        "SELECT * FROM tasks WHERE scheduled_at IS NOT NULL "
        "AND scheduled_at BETWEEN datetime('now') AND datetime('now', '+' || ? || ' hours') "
        "AND status != 'complete' ORDER BY scheduled_at ASC",
        (hours,),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_weekly_plan(week_start: str, week_end: str, focus: str, notes: str = None) -> None:
    _exec(
        "INSERT OR REPLACE INTO weekly_plans (week_start, week_end, focus, notes) "
        "VALUES (?, ?, ?, ?)",
        (week_start, week_end, focus, notes), commit=True,
    )


def get_current_weekly_plan() -> dict | None:
    today = datetime.now().strftime("%Y-%m-%d")
    row = _exec(
        "SELECT * FROM weekly_plans WHERE ? BETWEEN week_start AND week_end ORDER BY created_at DESC LIMIT 1",
        (today,),
    ).fetchone()
    return dict(row) if row else None


def add_commitment(description: str, deadline: str = None) -> int:
    cur = _exec(
        "INSERT INTO commitments (description, deadline) VALUES (?, ?)",
        (description, deadline),
        commit=True,
    )
    return cur.lastrowid


def list_commitments(status: str = None) -> list[dict]:
    if status:
        rows = _exec(
            "SELECT * FROM commitments WHERE status = ? ORDER BY id DESC",
            (status,),
        ).fetchall()
    else:
        rows = _exec(
            "SELECT * FROM commitments ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]
