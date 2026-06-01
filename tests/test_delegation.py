"""Tests for task delegation system."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import pytest
import sqlite3
import tempfile
from infra.db.task_queue import add_task, get_task_status, mark_complete, cancel_task, list_pending


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Create task_queue table with delegation columns
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE task_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT,
            message TEXT,
            priority TEXT DEFAULT 'normal',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            scheduled_for DATETIME,
            sent INTEGER DEFAULT 0,
            source TEXT DEFAULT 'autonomous',
            prompt TEXT,
            status TEXT DEFAULT 'queued',
            result TEXT,
            started_at TEXT,
            completed_at TEXT,
            duration_ms INTEGER
        )
    """)
    conn.commit()
    conn.close()
    
    # Override DB_PATH for the test
    import infra.db.schema
    original_path = infra.db.schema.DB_PATH
    infra.db.schema.DB_PATH = path
    infra.db.schema.init_db()
    
    yield path
    
    # Restore original path
    infra.db.schema.DB_PATH = original_path
    
    # Cleanup
    import time
    for _ in range(5):
        try:
            os.unlink(path)
            break
        except PermissionError:
            time.sleep(0.1)


def test_add_task_returns_integer_id(temp_db):
    """Test that add_task returns an integer task_id."""
    task_id = add_task(
        prompt="Test task",
        task_name="test_task",
        priority="normal"
    )
    assert isinstance(task_id, int)
    assert task_id > 0


def test_get_task_status_returns_queued_for_new_task(temp_db):
    """Test that get_task_status returns queued status for new task."""
    task_id = add_task(
        prompt="Test task",
        task_name="test_task"
    )
    task = get_task_status(task_id)
    assert task is not None
    assert task["status"] == "queued"
    assert task["prompt"] == "Test task"
    assert task["task_name"] == "test_task"


def test_mark_complete_updates_status_and_result(temp_db):
    """Test that mark_complete updates status, result, and duration."""
    task_id = add_task(
        prompt="Test task",
        task_name="test_task"
    )
    mark_complete(task_id, "Task completed successfully", 5000)
    
    task = get_task_status(task_id)
    assert task["status"] == "complete"
    assert task["result"] == "Task completed successfully"
    assert task["duration_ms"] == 5000
    assert task["completed_at"] is not None


def test_cancel_queued_task_returns_true(temp_db):
    """Test that cancel_task returns True for queued tasks."""
    task_id = add_task(
        prompt="Test task",
        task_name="test_task"
    )
    cancelled = cancel_task(task_id)
    assert cancelled is True
    
    task = get_task_status(task_id)
    assert task["status"] == "cancelled"


def test_cancel_running_task_returns_false(temp_db):
    """Test that cancel_task returns False for running tasks."""
    task_id = add_task(
        prompt="Test task",
        task_name="test_task"
    )
    # Mark as running (simulated by direct DB update)
    conn = sqlite3.connect(temp_db)
    conn.execute("UPDATE task_queue SET status = 'running' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    cancelled = cancel_task(task_id)
    assert cancelled is False
    
    task = get_task_status(task_id)
    assert task["status"] == "running"


def test_list_pending_excludes_completed_tasks(temp_db):
    """Test that list_pending excludes completed tasks."""
    # Add 3 tasks
    task1 = add_task(prompt="Task 1", task_name="task1")
    task2 = add_task(prompt="Task 2", task_name="task2")
    task3 = add_task(prompt="Task 3", task_name="task3")
    
    # Complete one
    mark_complete(task2, "Done", 1000)
    
    pending = list_pending()
    task_ids = [t["id"] for t in pending]
    
    assert task1 in task_ids
    assert task2 not in task_ids  # completed
    assert task3 in task_ids
    assert len(pending) == 2


def run_all() -> tuple[int, int]:
    import pytest
    _tests = [
        test_add_task_returns_integer_id,
        test_get_task_status_returns_queued_for_new_task,
        test_mark_complete_updates_status_and_result,
        test_cancel_queued_task_returns_true,
        test_cancel_running_task_returns_false,
        test_list_pending_excludes_completed_tasks,
    ]
    passed = failed = 0
    import sqlite3, tempfile, time
    for fn in _tests:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(path)
        conn.execute("""CREATE TABLE task_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT, task_name TEXT, message TEXT,
            priority TEXT DEFAULT 'normal', created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            scheduled_for DATETIME, sent INTEGER DEFAULT 0, source TEXT DEFAULT 'autonomous',
            prompt TEXT, status TEXT DEFAULT 'queued', result TEXT,
            started_at TEXT, completed_at TEXT, duration_ms INTEGER)""")
        conn.commit(); conn.close()
        import infra.db.schema as _schema
        orig = _schema.DB_PATH
        _schema.DB_PATH = path
        _schema.init_db()
        try:
            fn(path)
            print(f"  \u2713 delegation: {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 delegation: {fn.__name__}: {e}")
            failed += 1
        finally:
            _schema.DB_PATH = orig
            for _ in range(5):
                try: os.unlink(path); break
                except: time.sleep(0.1)
    return passed, failed
