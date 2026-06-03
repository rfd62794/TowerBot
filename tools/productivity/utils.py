"""Shared parsing utilities for productivity tools."""

import re
from datetime import datetime, timedelta

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
