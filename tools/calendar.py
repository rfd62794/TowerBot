"""Calendar tool functions — read-only Google Calendar integration."""

from datetime import datetime, timedelta, timezone

from tools.api.google_calendar_api import (
    get_events,
    get_events_today,
    get_events_window,
)
from tools.api._handler import BaseTool


class CalendarTools(BaseTool):
    """Calendar tool wrapper with BaseTool pattern."""
    
    def _format_event(self, event: dict) -> str:
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
    
    def get_today_schedule(self) -> dict:
        """All calendar events today."""
        raw = get_events_today()
        events = raw.get("events", [])
        
        return self.success({
            "count": len(events),
            "events": events,
            "formatted": [self._format_event(e) for e in events],
        }, stale_result=raw)
    
    def get_upcoming_events(self, days: int = 7) -> dict:
        """Events in the next N days."""
        raw = get_events(days_ahead=days)
        events = raw.get("events", [])
        
        return self.success({
            "count": len(events),
            "days": days,
            "events": events,
            "formatted": [self._format_event(e) for e in events],
        }, stale_result=raw)
    
    def check_availability(self, date: str) -> dict:
        """
        Is a specific date clear?
        date: YYYY-MM-DD
        Returns busy=True if any events exist, False if clear.
        """
        try:
            day = datetime.strptime(date, "%Y-%m-%d")
            start = day.replace(tzinfo=timezone.utc)
            end = start + timedelta(days=1)
            raw = get_events_window(start, end)
            events = raw.get("events", [])
        except Exception:
            events = []
        
        return self.success({
            "date": date,
            "busy": bool(events),
            "count": len(events),
            "events": events,
            "formatted": [self._format_event(e) for e in events],
        }, stale_result=raw)


# Module-level instance
calendar_tools = CalendarTools()

# Backwards compat
def _format_event(event: dict) -> str:
    return calendar_tools._format_event(event)

def get_today_schedule() -> dict:
    return calendar_tools.get_today_schedule()

def get_upcoming_events(days: int = 7) -> dict:
    return calendar_tools.get_upcoming_events(days)

def check_availability(date: str) -> dict:
    return calendar_tools.check_availability(date)
