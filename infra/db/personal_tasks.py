"""Personal task DB operations — standalone to-dos, reminders, recurring tasks."""

import calendar
import warnings
from datetime import datetime, timedelta

from infra.db.schema import _exec


def _compute_due_datetime(due_date: str | None, due_time: str | None) -> str | None:
    if due_date and due_time:
        return f"{due_date} {due_time}"
    if due_date:
        return due_date
    return None


def next_recurrence_date(recurrence: str, anchor: str) -> str:
    """
    Return next recurrence date from anchor date.
    
    Supported formats:
      "daily"           → anchor + 1 day
      "weekly:monday"   → next Monday from anchor, never same day
      "weekly:tuesday"  → next Tuesday, etc. (all 7 days)
      unknown format    → anchor + 1 day (safe fallback)
    
    "never same day" rule: if anchor is already the target weekday,
    return anchor + 7 days, not anchor.
    """
    try:
        base = datetime.fromisoformat(anchor[:10])

        if recurrence == "daily":
            return (base + timedelta(days=1)).strftime("%Y-%m-%d")

        if recurrence.startswith("weekly:"):
            day_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6,
            }
            target_day = recurrence[7:].strip().lower()
            if target_day not in day_map:
                # Unknown day, fallback to tomorrow
                return (base + timedelta(days=1)).strftime("%Y-%m-%d")
            
            target_weekday = day_map[target_day]
            nxt = base + timedelta(days=1)
            
            # Find next occurrence of target weekday
            for _ in range(7):
                if nxt.weekday() == target_weekday:
                    return nxt.strftime("%Y-%m-%d")
                nxt += timedelta(days=1)
            
            # Should never reach here, but fallback
            return (base + timedelta(days=7)).strftime("%Y-%m-%d")

        # Unknown format, safe fallback
        return (base + timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        # Any error, fallback to tomorrow
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")


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
    warnings.warn(
        "DEPRECATED (ADR-038): Direct access to 'personal_tasks' table. "
        "Use Google Tasks API tools instead. This will break in Phase 2.",
        DeprecationWarning,
        stacklevel=2
    )
    due_datetime = _compute_due_datetime(due_date, due_time)
    cur = _exec(
        "INSERT OR IGNORE INTO personal_tasks "
        "(title, notes, due_date, due_time, due_datetime, recurrence, "
        "reminder_minutes, next_due) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, notes, due_date, due_time, due_datetime,
         recurrence, reminder_minutes, due_datetime),
        commit=True,
    )
    return cur.lastrowid


def get_personal_tasks(filter: str = "today") -> list[dict]:
    warnings.warn(
        "DEPRECATED (ADR-038): Direct access to 'personal_tasks' table. "
        "Use Google Tasks API tools instead. This will break in Phase 2.",
        DeprecationWarning,
        stacklevel=2
    )
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
    warnings.warn(
        "DEPRECATED (ADR-038): Direct access to 'personal_tasks' table. "
        "Use Google Tasks API tools instead. This will break in Phase 2.",
        DeprecationWarning,
        stacklevel=2
    )
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
    warnings.warn(
        "DEPRECATED (ADR-038): Direct access to 'personal_tasks' table. "
        "Use Google Tasks API tools instead. This will break in Phase 2.",
        DeprecationWarning,
        stacklevel=2
    )
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
            new_datetime = _compute_due_datetime(next_date, task.get("due_time"))
            next_due_str = new_datetime
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
        "google_task_id": task.get("google_task_id"),
    }


def snooze_personal_task(task_id: int, minutes: int = 60) -> dict:
    warnings.warn(
        "DEPRECATED (ADR-038): Direct access to 'personal_tasks' table. "
        "Use Google Tasks API tools instead. This will break in Phase 2.",
        DeprecationWarning,
        stacklevel=2
    )
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
    warnings.warn(
        "DEPRECATED (ADR-038): Direct access to 'personal_tasks' table. "
        "Use Google Tasks API tools instead. This will break in Phase 2.",
        DeprecationWarning,
        stacklevel=2
    )
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


def push_missed_tasks() -> list[dict]:
    """
    Push forward all missed pending tasks to future dates.
    
    Query: due_date < today AND status = 'pending'
    For each row:
      - Recurring:     next_recurrence_date(recurrence, anchor=today)
      - Non-recurring: today + 1 day
    
    Collision check:
      If same title already pending at new_date, delete old row.
      Otherwise, UPDATE old row to new_date.
    
    Return list of pushed tasks: [{id, title, old_date, new_date}]
    """
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Find all missed pending tasks
    missed = _exec(
        "SELECT id, title, due_date, recurrence, due_time FROM personal_tasks "
        "WHERE due_date < ? AND status = 'pending'",
        (today,),
    ).fetchall()
    
    pushed = []
    
    for task in missed:
        task_dict = dict(task)
        task_id = task_dict["id"]
        title = task_dict["title"]
        old_date = task_dict["due_date"]
        recurrence = task_dict.get("recurrence")
        
        # Compute new date
        if recurrence:
            new_date = next_recurrence_date(recurrence, today)
        else:
            new_date = tomorrow
        
        # Collision check
        existing = _exec(
            "SELECT id FROM personal_tasks "
            "WHERE title = ? AND due_date = ? AND status = 'pending' AND id != ?",
            (title, new_date, task_id),
        ).fetchone()
        
        if existing:
            # Collision: delete old row, future row already covers it
            _exec("DELETE FROM personal_tasks WHERE id = ?", (task_id,), commit=True)
        else:
            # No collision: update old row
            new_datetime = _compute_due_datetime(new_date, task_dict.get("due_time"))
            _exec(
                "UPDATE personal_tasks "
                "SET due_date = ?, due_datetime = ? WHERE id = ?",
                (new_date, new_datetime, task_id),
                commit=True,
            )
        
        pushed.append({
            "id": task_id,
            "title": title,
            "old_date": old_date,
            "new_date": new_date,
        })
    
    return pushed


def set_google_task_id(task_id: int, google_task_id: str) -> None:
    _exec(
        "UPDATE personal_tasks SET google_task_id = ? WHERE id = ?",
        (google_task_id, task_id),
        commit=True,
    )


def get_unsynced_tasks() -> list[dict]:
    """Tasks with no google_task_id that are still pending."""
    rows = _exec(
        "SELECT * FROM personal_tasks "
        "WHERE google_task_id IS NULL AND status = 'pending' "
        "ORDER BY id ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_tasks_completed_since(since) -> list[dict]:
    """Tasks completed after since (ISO string or datetime), with google_task_id set."""
    if isinstance(since, datetime):
        since = since.isoformat()
    rows = _exec(
        "SELECT * FROM personal_tasks "
        "WHERE completed_at >= ? AND google_task_id IS NOT NULL",
        (since,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_sync_record(
    last_pull=None,
    last_push=None,
    tasklist_id=None,
    error=False,
) -> None:
    existing = _exec("SELECT id FROM tasks_sync LIMIT 1").fetchone()
    if not existing:
        _exec(
            "INSERT INTO tasks_sync "
            "(last_pull, last_push, tasklist_id, pull_count, push_count, error_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                last_pull, last_push, tasklist_id,
                1 if last_pull else 0,
                1 if last_push else 0,
                1 if error else 0,
            ),
            commit=True,
        )
    else:
        set_parts = []
        params = []
        if last_pull is not None:
            set_parts.extend(["last_pull = ?", "pull_count = pull_count + 1"])
            params.append(last_pull)
        if last_push is not None:
            set_parts.extend(["last_push = ?", "push_count = push_count + 1"])
            params.append(last_push)
        if tasklist_id is not None:
            set_parts.append("tasklist_id = ?")
            params.append(tasklist_id)
        if error:
            set_parts.append("error_count = error_count + 1")
        if set_parts:
            params.append(existing["id"])
            _exec(
                f"UPDATE tasks_sync SET {', '.join(set_parts)} WHERE id = ?",
                tuple(params),
                commit=True,
            )


def get_last_sync() -> dict | None:
    row = _exec("SELECT * FROM tasks_sync LIMIT 1").fetchone()
    return dict(row) if row else None


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
