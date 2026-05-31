# Google Phase 2 Migration Plan

Migrate gmail_api.py, google_calendar_api.py, google_tasks_api.py to BaseAPIHandler pattern. Handle account params in cache keys, type changes (int/list → dict), write operations bypassing cache, test updates, TTL additions. Target: 179/179 tests passing.

## Part 1: Gmail API Migration (tools/api/gmail_api.py)
- Create GmailAPIHandler(BaseAPIHandler) with CACHE_PREFIX="gmail"
- _get_client(account) routes to personal or rfd credentials
- get_unread_count: returns {"count": int, "account": str, "authorized": bool}, hash includes label+account
- search_messages: returns {"messages": list, "account": str, "authorized": bool}, hash includes query+max_results+account
- get_message_body: returns {"body": str, "account": str}, hash includes message_id+account
- get_recent_unread: delegates to search_messages
- get_messages_from: delegates to search_messages
- Module-level gmail_api instance + backwards compat functions

## Part 2: Gmail Tool Layer (tools/gmail.py)
- Unwrap dict returns from gmail_api functions
- get_inbox_summary: raw.get("count", 0) instead of direct int
- get_all_inbox_summary: same unwrapping
- search_email, check_sender, check_sender_all, read_email: unwrap "messages" from dict
- Add stale_result=raw to self.success() calls

## Part 3: Gmail Tests (tests/test_gmail.py)
- test_unread_count: assert dict with "count" key instead of int
- test_recent_unread: assert dict with "messages" key instead of list
- test_search_messages: assert dict with "messages" key
- test_messages_from: assert dict with "messages" key
- Other tests unchanged (tool layer already returns dict)

## Part 4: Gmail TTL (core/cache.py)
Add if missing:
- gmail_unread_personal: 300
- gmail_unread_rfd: 300
- gmail_search_personal: 300
- gmail_search_rfd: 300
- gmail_body_personal: 3600
- gmail_body_rfd: 3600
Add corresponding STALE_BUDGET entries

## Part 5: Calendar API Migration (tools/api/google_calendar_api.py)
- Create CalendarAPIHandler(BaseAPIHandler) with CACHE_PREFIX="calendar"
- get_events: returns {"events": list, "calendar_id": str}, stale_ok=True
- get_events_window: returns {"events": list}, stale_ok=True
- get_events_today: returns {"events": list, "date": str}, stale_ok=True
- get_events_soon: returns {"events": list, "window_minutes": int}, stale_ok=False (time-sensitive)
- Module-level calendar_api instance + backwards compat functions

## Part 6: Calendar Tool Layer (tools/calendar.py)
- Unwrap dict returns: raw.get("events", [])
- get_today_schedule, get_upcoming_events, check_availability: same pattern
- Add stale_result=raw to self.success() calls

## Part 7: Calendar Tests (tests/test_google_calendar.py)
- test_get_events: assert dict with "events" key instead of list
- test_get_events_today: assert dict with "events" key
- Other tests unchanged (tool layer already returns dict)

## Part 8: Calendar TTL (core/cache.py)
Add if missing:
- calendar_upcoming: 900
- calendar_window: 900
- calendar_today: 900
- calendar_soon: 300
Add corresponding STALE_BUDGET entries

## Part 9: Tasks API Migration (tools/api/google_tasks_api.py)
- Create TasksAPIHandler(BaseAPIHandler) with CACHE_PREFIX="google_tasks"
- READ operations use self.call():
  - get_default_tasklist_id: returns {"tasklist_id": str}, stale_ok=True
  - pull_tasks: returns {"tasks": list, "tasklist_id": str}, stale_ok=True
- WRITE operations bypass cache (direct execution):
  - push_task: direct try/except, returns dict | None
  - complete_task: direct try/except, returns bool
  - delete_task: direct try/except, returns bool
- Module-level tasks_api instance + backwards compat functions

## Part 10: Tasks Sync (tools/sync_tasks.py)
- get_or_cache_tasklist_id: unwrap raw.get("tasklist_id")
- pull_from_google: unwrap raw.get("tasks", [])

## Part 11: Tasks Tests (tests/test_google_tasks_sync.py)
- test_get_default_tasklist_id: assert dict with "tasklist_id" key instead of str
- test_pull_tasks: assert dict with "tasks" key instead of list
- test_push_task: unchanged (write operation still returns dict | None)
- test_run_sync: unchanged (returns status dict)

## Part 12: Tasks TTL (core/cache.py)
Add if missing:
- google_tasks_tasklist_id: 300
- google_tasks_tasks: 300
Add corresponding STALE_BUDGET entries

## Part 13: Scheduler Heartbeat (core/scheduler.py)
- Update get_events_soon call: raw.get("events", []) instead of direct list

## Part 14: Verification
Run uv run python scripts/verify.py — expect 179/179 passed

## Part 15: Spot Check
Test get_all_inbox_summary, get_today_schedule, run_sync

## Files Modified
- tools/api/gmail_api.py
- tools/api/google_calendar_api.py
- tools/api/google_tasks_api.py
- tools/gmail.py
- tools/calendar.py
- tools/sync_tasks.py
- core/scheduler.py
- tests/test_gmail.py
- tests/test_google_calendar.py
- tests/test_google_tasks_sync.py
- core/cache.py
