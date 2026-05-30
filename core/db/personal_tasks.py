"""Personal task DB operations — standalone to-dos, reminders, recurring tasks."""

import calendar
from datetime import datetime, timedelta

from core.db.schema import _exec


def _compute_due_datetime(due_date: str | None, due_time: str | None) -> str | None:
    if due_date and due_time:
        return f"{due_date} {due_time}"
    if due_date:
        return due_date
    return None


def _calc_next_due(recurrence: str, from_date: str) -> str | None:
    """Return next due date string given a recurrence pattern and base date."""
    try:
        base = datetime.fromisoformat(from_date[:10])

        if recurrence == "daily":
            return (base + timedelta(days=1)).strftime("%Y-%m-%d")

        if recurrence == "weekdays":
            nxt = base + timedelta(days=1)
            while nxt.weekday() >= 5:
                nxt += timedelta(days=1)
            return nxt.strftime("%Y-%m-%d")

        if recurrence == "weekends":
            nxt = base + timedelta(days=1)
            while nxt.weekday() < 5:
                nxt += timedelta(days=1)
            return nxt.strftime("%Y-%m-%d")

        if recurrence.startswith("weekly:"):
            day_names = recurrence[7:].split(",")
            day_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6,
            }
            targets = [day_map[d.strip()] for d in day_names if d.strip() in day_map]
            if not targets:
                return None
            nxt = base + timedelta(days=1)
            for _ in range(7):
                if nxt.weekday() in targets:
                    return nxt.strftime("%Y-%m-%d")
                nxt += timedelta(days=1)
            return None

        if recurrence.startswith("monthly:"):
            day_of_month = int(recurrence[8:])
            yr = base.year + 1 if base.month == 12 else base.year
            mo = 1 if base.month == 12 else base.month + 1
            max_day = calendar.monthrange(yr, mo)[1]
            return datetime(yr, mo, min(day_of_month, max_day)).strftime("%Y-%m-%d")

        if recurrence == "monthly":
            yr = base.year + 1 if base.month == 12 else base.year
            mo = 1 if base.month == 12 else base.month + 1
            max_day = calendar.monthrange(yr, mo)[1]
            return datetime(yr, mo, min(base.day, max_day)).strftime("%Y-%m-%d")

        if recurrence.startswith("interval:"):
            days = int(recurrence[9:])
            return (base + timedelta(days=days)).strftime("%Y-%m-%d")

        return None
    except Exception:
        return None


def add_personal_task(
    title: str,
    due_date: str = None,
    due_time: str = None,
    recurrence: str = None,
    notes: str = None,
    reminder_minutes: int = 30,
) -> int:
    due_datetime = _compute_due_datetime(due_date, due_time)
    cur = _exec(
        "INSERT INTO personal_tasks "
        "(title, notes, due_date, due_time, due_datetime, recurrence, "
        "reminder_minutes, next_due) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, notes, due_date, due_time, due_datetime,
         recurrence, reminder_minutes, due_datetime),
        commit=True,
    )
    return cur.lastrowid


def get_personal_tasks(filter: str = "today") -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    week_end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    if filter == "today":
        rows = _exec(
            "SELECT * FROM personal_tasks "
            "WHERE due_date = ? AND status = 'pending' "
            "ORDER BY due_time ASC, id ASC",
            (today,),
        ).fetchall()
    elif filter == "upcoming":
        rows = _exec(
            "SELECT * FROM personal_tasks "
            "WHERE due_date BETWEEN ? AND ? AND status = 'pending' "
            "ORDER BY due_date ASC, due_time ASC",
            (today, week_end),
        ).fetchall()
    elif filter == "overdue":
        rows = _exec(
            "SELECT * FROM personal_tasks "
            "WHERE due_date < ? AND status = 'pending' "
            "ORDER BY due_date ASC",
            (today,),
        ).fetchall()
    else:
        rows = _exec(
            "SELECT * FROM personal_tasks "
            "WHERE status = 'pending' "
            "ORDER BY due_date ASC, due_time ASC, id ASC"
        ).fetchall()

    return [dict(r) for r in rows]


def get_tasks_due_soon(minutes: int = 90) -> list[dict]:
    """Return pending personal tasks with due_datetime within the next N minutes."""
    rows = _exec(
        "SELECT * FROM personal_tasks "
        "WHERE due_datetime BETWEEN datetime('now', 'localtime') "
        "AND datetime('now', 'localtime', '+' || ? || ' minutes') "
        "AND status = 'pending' "
        "ORDER BY due_datetime ASC",
        (minutes,),
    ).fetchall()
    return [dict(r) for r in rows]


def complete_personal_task(task_id: int) -> dict:
    row = _exec(
        "SELECT * FROM personal_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if not row:
        return {"error": f"Task not found: {task_id}"}

    task = dict(row)
    _exec(
        "UPDATE personal_tasks SET status = 'done', "
        "completed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (task_id,),
        commit=True,
    )

    next_due_str = None
    if task.get("recurrence"):
        base = task.get("due_date") or datetime.now().strftime("%Y-%m-%d")
        next_date = _calc_next_due(task["recurrence"], base)
        if next_date:
            next_due_str = next_date
            new_datetime = _compute_due_datetime(next_date, task.get("due_time"))
            _exec(
                "INSERT INTO personal_tasks "
                "(title, notes, due_date, due_time, due_datetime, recurrence, "
                "reminder_minutes, next_due) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (task["title"], task.get("notes"), next_date, task.get("due_time"),
                 new_datetime, task["recurrence"],
                 task.get("reminder_minutes", 30), new_datetime),
                commit=True,
            )

    return {
        "status": "completed",
        "id": task_id,
        "title": task["title"],
        "next_due": next_due_str,
    }


def snooze_personal_task(task_id: int, minutes: int = 60) -> dict:
    row = _exec(
        "SELECT * FROM personal_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if not row:
        return {"error": f"Task not found: {task_id}"}

    task = dict(row)
    if task.get("due_datetime"):
        try:
            current = datetime.fromisoformat(task["due_datetime"].replace(" ", "T"))
        except Exception:
            current = datetime.now()
    else:
        current = datetime.now()

    new_dt = current + timedelta(minutes=minutes)
    new_dt_str = new_dt.strftime("%Y-%m-%d %H:%M")
    new_date = new_dt.strftime("%Y-%m-%d")
    new_time = new_dt.strftime("%H:%M")

    _exec(
        "UPDATE personal_tasks "
        "SET due_datetime = ?, due_date = ?, due_time = ? WHERE id = ?",
        (new_dt_str, new_date, new_time, task_id),
        commit=True,
    )
    return {"status": "snoozed", "id": task_id, "new_due": new_dt_str}


def delete_personal_task(task_id: int) -> dict:
    row = _exec(
        "SELECT * FROM personal_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if not row:
        return {"error": f"Task not found: {task_id}"}

    _exec(
        "UPDATE personal_tasks SET status = 'cancelled' WHERE id = ?",
        (task_id,),
        commit=True,
    )
    return {"status": "deleted", "id": task_id}


def mark_reminded(task_id: int) -> None:
    _exec(
        "INSERT INTO task_reminders (task_id) VALUES (?)",
        (task_id,),
        commit=True,
    )


def already_reminded(task_id: int) -> bool:
    row = _exec(
        "SELECT id FROM task_reminders "
        "WHERE task_id = ? AND reminded_at > datetime('now', '-60 minutes')",
        (task_id,),
    ).fetchone()
    return row is not None
