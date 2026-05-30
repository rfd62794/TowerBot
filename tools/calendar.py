"""Calendar tool functions — read-only Google Calendar integration."""

from datetime import datetime, timedelta, timezone

from tools.api.google_calendar_api import (
    get_events,
    get_events_today,
    get_events_window,
)


def _format_event(event: dict) -> str:
    """Format a single calendar event as a readable string."""
    if event["all_day"]:
        time_str = "all day"
    else:
        try:
            dt = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
            local_dt = dt.astimezone()
            hour = local_dt.hour
            minute = local_dt.minute
            meridiem = "AM" if hour < 12 else "PM"
            display_hour = hour % 12 or 12
            time_str = f"{display_hour}:{minute:02d} {meridiem}"
        except Exception:
            time_str = event["start"][:16] if event["start"] else "?"

    result = f"{time_str} — {event['title']}"
    if event.get("location"):
        result += f" @ {event['location']}"
    return result


def get_today_schedule() -> dict:
    """All calendar events today."""
    events = get_events_today()
    return {
        "count": len(events),
        "events": events,
        "formatted": [_format_event(e) for e in events],
    }


def get_upcoming_events(days: int = 7) -> dict:
    """Events in the next N days."""
    events = get_events(days_ahead=days)
    return {
        "count": len(events),
        "days": days,
        "events": events,
        "formatted": [_format_event(e) for e in events],
    }


def check_availability(date: str) -> dict:
    """
    Is a specific date clear?
    date: YYYY-MM-DD
    Returns busy=True if any events exist, False if clear.
    """
    try:
        day = datetime.strptime(date, "%Y-%m-%d")
        start = day.replace(tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        events = get_events_window(start, end)
    except Exception:
        events = []

    return {
        "date": date,
        "busy": bool(events),
        "count": len(events),
        "events": events,
        "formatted": [_format_event(e) for e in events],
    }
