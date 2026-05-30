"""Tests for core/db/ package — schema, CRUD, cache, history."""

import sys
import os
import sqlite3

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


@test("db: all core tables exist")
def test_all_tables():
    conn = sqlite3.connect(os.path.join(_root, "privy.db"))
    tables = {t[0] for t in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    for t in ("threads", "messages", "memory", "model_status", "kv_cache",
              "tool_cache", "channel_history", "video_history", "game_history",
              "weather_history", "video_metadata_cache", "scheduled_videos",
              "task_queue", "goals", "milestones", "tasks", "weekly_plans"):
        assert t in tables, f"Missing table: {t}"


@test("db: add_message and get_context round trip")
def test_message_roundtrip():
    from core.db import create_thread, add_message, get_context
    tid = "test_verify_thread_001"
    try:
        create_thread(tid)
    except Exception:
        pass
    add_message(tid, "user", "hello from test")
    ctx = get_context(tid, n=5)
    assert any(m["content"] == "hello from test" for m in ctx), \
        "Message not found in context"


@test("db: save_memory and list_memories round trip")
def test_memory_roundtrip():
    from core.db import save_memory, list_memories
    save_memory("test_verify_key", "test_verify_value", "technical")
    memories = list_memories()
    assert any(m["key"] == "test_verify_key" for m in memories), \
        "Saved memory not found in list"


@test("db: cache_tool_result and get_cached_tool_result round trip")
def test_tool_cache_roundtrip():
    from core.db import cache_tool_result, get_cached_tool_result
    cache_tool_result("test_tool", "test_hash_abc", {"value": 42}, ttl_hours=1)
    result = get_cached_tool_result("test_tool", "test_hash_abc")
    assert result is not None, "Cached result not found"
    assert result["value"] == 42, f"Expected 42, got {result['value']}"


@test("db: cache miss returns None for expired/nonexistent")
def test_tool_cache_miss():
    from core.db import get_cached_tool_result
    result = get_cached_tool_result("nonexistent_tool", "nonexistent_hash_xyz")
    assert result is None, "Expected None for cache miss"


@test("db: record_channel_day and get_channel_history round trip")
def test_channel_history_roundtrip():
    from core.db import record_channel_day, get_channel_history
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    record_channel_day(today, 9876, 55.5, 2)
    history = get_channel_history(days=1)
    assert any(h["date"] == today for h in history), \
        "Channel day not found in history"


@test("db: queue_observation and get_pending_observations round trip")
def test_queue_roundtrip():
    from core.db import queue_observation, get_pending_observations, mark_sent
    queue_observation("test_task", "test message for verify", priority="normal")
    pending = get_pending_observations()
    found = [o for o in pending if o["task_name"] == "test_task"
             and o["message"] == "test message for verify"]
    assert len(found) > 0, "Queued observation not found in pending"
    mark_sent(found[0]["id"])
    pending2 = get_pending_observations()
    assert not any(o["id"] == found[0]["id"] for o in pending2), \
        "Observation still pending after mark_sent"


@test("db: create_thread and update_thread_name round trip")
def test_thread_roundtrip():
    from core.db import create_thread, update_thread_name, list_threads
    tid = "test_verify_thread_name_001"
    try:
        create_thread(tid)
    except Exception:
        pass
    update_thread_name(tid, "Test Thread Name")
    threads = list_threads(limit=100)
    match = [t for t in threads if t["id"] == tid]
    assert len(match) > 0, "Thread not found after creation"
    assert match[0]["name"] == "Test Thread Name", \
        f"Expected 'Test Thread Name', got {match[0]['name']}"


@test("db: upsert_goal and get_goal round trip")
def test_goal_roundtrip():
    from core.db import upsert_goal, get_goal
    upsert_goal("test_verify_goal_001", "Test Goal", "A test goal",
                "2099-12-31", status="active")
    goal = get_goal("test_verify_goal_001")
    assert goal is not None, "Goal not found after upsert"
    assert goal["title"] == "Test Goal", \
        f"Expected 'Test Goal', got {goal['title']}"


@test("db: upsert_task and get_tasks_due_today")
def test_task_roundtrip():
    from core.db import upsert_task, get_tasks_due_today, update_task_status, get_task
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    upsert_task("test_verify_task_001", "Test Task", today, status="pending")
    tasks = get_tasks_due_today()
    assert isinstance(tasks, list), "get_tasks_due_today should return list"
    found = [t for t in tasks if t["id"] == "test_verify_task_001"]
    assert len(found) > 0, "Task not found in today's tasks"
    update_task_status("test_verify_task_001", "complete")
    task = get_task("test_verify_task_001")
    assert task["status"] == "complete", \
        f"Expected 'complete', got {task['status']}"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
