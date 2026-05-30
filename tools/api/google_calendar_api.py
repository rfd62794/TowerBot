"""Google Calendar API client — raw API calls only. Read-only."""

from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build
from tools.api.youtube_api import _get_credentials


def _get_calendar_client():
    creds = _get_credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _parse_event(item: dict, calendar_id: str) -> dict:
    """Normalize a Google Calendar event item to a flat dict."""
    start_info = item.get("start", {})
    end_info = item.get("end", {})
    all_day = "dateTime" not in start_info
    start = start_info.get("dateTime") or start_info.get("date", "")
    end = end_info.get("dateTime") or end_info.get("date", "")
    return {
        "id": item.get("id", ""),
        "title": item.get("summary", "(no title)"),
        "start": start,
        "end": end,
        "location": item.get("location"),
        "description": item.get("description"),
        "all_day": all_day,
        "calendar_id": calendar_id,
    }


def _parse_events(items: list, calendar_id: str) -> list[dict]:
    return [_parse_event(item, calendar_id) for item in items]


def get_events(
    calendar_id: str = "primary",
    days_ahead: int = 7,
    max_results: int = 20,
) -> list[dict]:
    try:
        client = _get_calendar_client()
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        result = client.events().list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return _parse_events(result.get("items", []), calendar_id)
    except Exception:
        return []


def get_events_window(
    time_min: datetime,
    time_max: datetime,
    calendar_id: str = "primary",
    max_results: int = 20,
) -> list[dict]:
    try:
        client = _get_calendar_client()
        result = client.events().list(
            calendarId=calendar_id,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return _parse_events(result.get("items", []), calendar_id)
    except Exception:
        return []


def get_events_today(calendar_id: str = "primary") -> list[dict]:
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return get_events_window(start_of_day, end_of_day, calendar_id)


def get_events_soon(
    minutes: int = 60,
    calendar_id: str = "primary",
) -> list[dict]:
    """Events starting within the next N minutes. Adds minutes_until to each."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(minutes=minutes)
    events = get_events_window(now, end, calendar_id)
    for event in events:
        if not event["all_day"] and event["start"]:
            try:
                dt = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
                event["minutes_until"] = max(0, int((dt - now).total_seconds() / 60))
            except Exception:
                event["minutes_until"] = None
        else:
            event["minutes_until"] = None
    return events
