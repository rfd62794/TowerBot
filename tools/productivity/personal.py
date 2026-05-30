"""Personal task tools — standalone reminders and to-dos."""

import re
from datetime import datetime, timedelta

from infra.db.personal_tasks import (
    add_personal_task as _db_add,
    get_personal_tasks as _db_get,
    complete_personal_task as _db_complete,
    snooze_personal_task as _db_snooze,
    delete_personal_task as _db_delete,
)

_DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_RECURRENCE_PATTERN = re.compile(
    r'^(daily|weekdays|weekends|weekly:|monthly|interval:)'
)


def parse_natural_deadline(text: str) -> dict:
    """
    Parse natural language date/time into {date, time}.
    Returns: {"date": "YYYY-MM-DD" or None, "time": "HH:MM" or None}
    """
    text_lower = text.lower().strip()
    today = datetime.now()
    result = {"date": None, "time": None}

    if _DATE_PATTERN.match(text_lower):
        result["date"] = text_lower
        return result

    time_match = re.search(r'\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text_lower)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        meridiem = time_match.group(3)
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        result["time"] = f"{hour:02d}:{minute:02d}"

    if "today" in text_lower:
        result["date"] = today.strftime("%Y-%m-%d")
    elif "tomorrow" in text_lower:
        result["date"] = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "next week" in text_lower:
        days_ahead = 7 - today.weekday()
        result["date"] = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    else:
        day_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
        }
        for day_name, day_num in day_map.items():
            if day_name in text_lower:
                days_ahead = (day_num - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                result["date"] = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                break

    return result


def parse_recurrence(text: str) -> str | None:
    """
    Detect recurrence pattern in natural language.
    Returns pattern string or None.
    """
    text_lower = text.lower()

    if "every day" in text_lower or text_lower.strip() == "daily":
        return "daily"
    if "every weekday" in text_lower or "every work day" in text_lower:
        return "weekdays"
    if "every weekend" in text_lower:
        return "weekends"

    interval_match = re.search(r'every\s+(\d+)\s+(day|week)', text_lower)
    if interval_match:
        n = int(interval_match.group(1))
        unit = interval_match.group(2)
        return f"interval:{n}" if unit == "day" else f"interval:{n * 7}"

    day_names = ["monday", "tuesday", "wednesday", "thursday",
                 "friday", "saturday", "sunday"]
    for day in day_names:
        if f"every {day}" in text_lower:
            return f"weekly:{day}"

    if "every week" in text_lower:
        current_day = day_names[datetime.now().weekday()]
        return f"weekly:{current_day}"

    if "every month" in text_lower or text_lower.strip() == "monthly":
        return "monthly"

    return None


def add_personal_task(
    title: str,
    due: str = None,
    time: str = None,
    recurrence: str = None,
    notes: str = None,
) -> dict:
    """Add a personal to-do or reminder with optional natural language deadline."""
    due_date = None
    due_time = time

    if due:
        if _DATE_PATTERN.match(due):
            due_date = due
        else:
            parsed = parse_natural_deadline(due)
            due_date = parsed.get("date")
            if not due_time:
                due_time = parsed.get("time")

    parsed_recurrence = recurrence
    if recurrence and not _RECURRENCE_PATTERN.match(recurrence):
        parsed_recurrence = parse_recurrence(recurrence)

    task_id = _db_add(
        title=title,
        due_date=due_date,
        due_time=due_time,
        recurrence=parsed_recurrence,
        notes=notes,
    )

    # Event-driven push to Google Tasks
    try:
        from tools.productivity.sync import get_or_cache_tasklist_id
        from tools.api.google_tasks_api import push_task as _push_gtask
        from infra.db.personal_tasks import set_google_task_id
        tasklist_id = get_or_cache_tasklist_id()
        if tasklist_id:
            g_result = _push_gtask(tasklist_id, title=title, notes=notes, due=due_date)
            if g_result:
                set_google_task_id(task_id, g_result["id"])
    except Exception:
        pass  # Local task created; sync will catch it on next heartbeat

    due_str = (
        f"{due_date} {due_time}" if due_time else
        due_date if due_date else "no deadline"
    )
    return {
        "status": "added",
        "id": task_id,
        "title": title,
        "due": due_str,
        "recurrence": parsed_recurrence,
    }


def list_personal_tasks(filter: str = "today") -> dict:
    """List personal tasks by filter: today / upcoming / overdue / all."""
    tasks = _db_get(filter=filter)
    return {
        "filter": filter,
        "count": len(tasks),
        "tasks": [
            {
                "id": t["id"],
                "title": t["title"],
                "due_date": t.get("due_date"),
                "due_time": t.get("due_time"),
                "recurrence": t.get("recurrence"),
                "status": t["status"],
            }
            for t in tasks
        ],
    }


def complete_personal_task(task_id: int) -> dict:
    """Mark a personal task done. If recurring, creates next occurrence."""
    result = _db_complete(task_id)

    # Event-driven push completion to Google Tasks
    if result.get("status") == "completed" and result.get("google_task_id"):
        try:
            from tools.productivity.sync import get_or_cache_tasklist_id
            from tools.api.google_tasks_api import complete_task as _complete_gtask
            tasklist_id = get_or_cache_tasklist_id()
            if tasklist_id:
                _complete_gtask(tasklist_id, result["google_task_id"])
        except Exception:
            pass

    return result


def snooze_personal_task(task_id: int, minutes: int = 60) -> dict:
    """Push a task's due time forward by N minutes."""
    return _db_snooze(task_id, minutes)


def delete_personal_task(task_id: int) -> dict:
    """Cancel/delete a personal task."""
    return _db_delete(task_id)
