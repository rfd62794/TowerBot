"""Tests for Google Calendar integration."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from core.db import init_db
init_db()

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


@test("calendar: credentials load")
def test_credentials():
    from tools.api.google_calendar_api import _get_calendar_client
    client = _get_calendar_client()
    assert client is not None


@test("calendar: get_events returns dict with events")
def test_get_events():
    from tools.api.google_calendar_api import get_events
    result = get_events(days_ahead=7)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "events" in result, "Missing 'events' key"
    assert isinstance(result["events"], list), f"Expected list for events, got {type(result['events'])}"


@test("calendar: get_events_today returns dict with events")
def test_get_events_today():
    from tools.api.google_calendar_api import get_events_today
    result = get_events_today()
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "events" in result, "Missing 'events' key"
    assert isinstance(result["events"], list), f"Expected list for events, got {type(result['events'])}"


@test("calendar: get_today_schedule returns dict with count and formatted")
def test_get_today_schedule():
    from tools.calendar import get_today_schedule
    result = get_today_schedule()
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "count" in result, "Missing 'count' key"
    assert "formatted" in result, "Missing 'formatted' key"
    assert isinstance(result["formatted"], list)


@test("calendar: get_upcoming_events returns dict")
def test_get_upcoming_events():
    from tools.calendar import get_upcoming_events
    result = get_upcoming_events(days=7)
    assert isinstance(result, dict)
    assert "count" in result
    assert "days" in result
    assert result["days"] == 7


@test("calendar: check_availability returns busy bool")
def test_check_availability():
    from tools.calendar import check_availability
    from datetime import datetime, timedelta
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    result = check_availability(future_date)
    assert isinstance(result, dict)
    assert "busy" in result
    assert isinstance(result["busy"], bool)
    assert "date" in result
    assert result["date"] == future_date


@test("calendar: _format_event handles all-day event")
def test_format_all_day():
    from tools.calendar import _format_event
    event = {
        "id": "test1",
        "title": "Holiday",
        "start": "2026-06-01",
        "end": "2026-06-02",
        "location": None,
        "description": None,
        "all_day": True,
        "calendar_id": "primary",
    }
    result = _format_event(event)
    assert "all day" in result
    assert "Holiday" in result


@test("calendar: _format_event handles timed event")
def test_format_timed():
    from tools.calendar import _format_event
    event = {
        "id": "test2",
        "title": "Dentist",
        "start": "2026-06-01T14:00:00-04:00",
        "end": "2026-06-01T15:00:00-04:00",
        "location": "123 Main St",
        "description": None,
        "all_day": False,
        "calendar_id": "primary",
    }
    result = _format_event(event)
    assert "Dentist" in result
    assert "123 Main St" in result
    assert "PM" in result or "AM" in result


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
