"""Google Calendar API client — raw API calls only. Read-only."""

from datetime import datetime, timedelta, timezone
import logging

from googleapiclient.discovery import build
from api.google.youtube_api import _get_credentials
from api._handler import BaseAPIHandler

logger = logging.getLogger("privy.calendar_api")


class CalendarAPIHandler(BaseAPIHandler):
    """Google Calendar API handler with caching."""
    
    CACHE_PREFIX = "calendar"
    
    def _get_client(self):
        creds = _get_credentials()
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    
    def _parse_event(self, item: dict, calendar_id: str) -> dict:
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
    
    def _parse_events(self, items: list, calendar_id: str) -> list[dict]:
        return [self._parse_event(item, calendar_id) for item in items]
    
    def get_events(self, calendar_id: str = "primary", days_ahead: int = 7, max_results: int = 20) -> dict:
        params_hash = self.hash(calendar_id, days_ahead, max_results)
        
        def _live() -> dict:
            client = self._get_client()
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
            events_list = self._parse_events(result.get("items", []), calendar_id)
            return {"events": events_list, "calendar_id": calendar_id}
        
        return self.call("upcoming", params_hash, _live, stale_ok=True)
    
    def get_events_window(self, time_min: datetime, time_max: datetime, calendar_id: str = "primary", max_results: int = 20) -> dict:
        params_hash = self.hash(time_min.isoformat(), time_max.isoformat(), calendar_id, max_results)
        
        def _live() -> dict:
            client = self._get_client()
            result = client.events().list(
                calendarId=calendar_id,
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            events_list = self._parse_events(result.get("items", []), calendar_id)
            return {"events": events_list}
        
        return self.call("window", params_hash, _live, stale_ok=True)
    
    def get_events_today(self, calendar_id: str = "primary") -> dict:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
        today_str = now.strftime("%Y-%m-%d")
        params_hash = self.hash(today_str, calendar_id)
        
        def _live() -> dict:
            events_list = self.get_events_window(start_of_day, end_of_day, calendar_id).get("events", [])
            return {"events": events_list, "date": today_str}
        
        return self.call("today", params_hash, _live, stale_ok=True)
    
    def get_events_soon(self, minutes: int = 60, calendar_id: str = "primary") -> dict:
        """Events starting within the next N minutes. Adds minutes_until to each."""
        params_hash = self.hash(minutes, calendar_id)
        
        def _live() -> dict:
            now = datetime.now(timezone.utc)
            end = now + timedelta(minutes=minutes)
            events_list = self.get_events_window(now, end, calendar_id).get("events", [])
            for event in events_list:
                if not event["all_day"] and event["start"]:
                    try:
                        dt = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
                        event["minutes_until"] = max(0, int((dt - now).total_seconds() / 60))
                    except Exception:
                        event["minutes_until"] = None
                else:
                    event["minutes_until"] = None
            return {"events": events_list, "window_minutes": minutes}
        
        return self.call("soon", params_hash, _live, stale_ok=False)


# Module-level instance
calendar_api = CalendarAPIHandler()

# Backwards compat
def get_events(calendar_id="primary", days_ahead=7, max_results=20):
    return calendar_api.get_events(calendar_id, days_ahead, max_results)

def get_events_window(time_min, time_max, calendar_id="primary", max_results=20):
    return calendar_api.get_events_window(time_min, time_max, calendar_id, max_results)

def get_events_today(calendar_id="primary"):
    return calendar_api.get_events_today(calendar_id)

def get_events_soon(minutes=60, calendar_id="primary"):
    return calendar_api.get_events_soon(minutes, calendar_id)

# Backwards compat for test imports
def _get_calendar_client():
    return calendar_api._get_client()
