"""Tests for database sync system."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import pytest
import sqlite3
import tempfile
import json
from infra.db.sync import DBSync, SyncPolicy, classify_unknown_table, ConflictStrategy, TABLE_REGISTRY


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Create test tables
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            content TEXT,
            layer TEXT,
            created DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE tool_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT,
            cache_key TEXT,
            data TEXT,
            expires_at DATETIME
        )
    """)
    conn.commit()
    conn.close()
    
    yield path
    
    # Cleanup - retry for Windows file locking
    import time
    for _ in range(5):
        try:
            os.unlink(path)
            break
        except PermissionError:
            time.sleep(0.1)


def test_classify_known_table_returns_correct_policy():
    """Test that known tables return correct sync policies."""
    assert TABLE_REGISTRY["memory"] == SyncPolicy.SHARED
    assert TABLE_REGISTRY["messages"] == SyncPolicy.INSTANCE
    assert TABLE_REGISTRY["tool_cache"] == SyncPolicy.CACHE
    assert TABLE_REGISTRY["bot_state"] == SyncPolicy.CONFIG


def test_classify_unknown_uses_heuristics():
    """Test that unknown tables are classified using heuristics."""
    # Cache-like name
    assert classify_unknown_table("test_cache", ["id", "data"]) == SyncPolicy.CACHE
    
    # Log-like name
    assert classify_unknown_table("test_log", ["id", "message"]) == SyncPolicy.CACHE
    
    # History-like name
    assert classify_unknown_table("test_history", ["id", "value"]) == SyncPolicy.CACHE
    
    # Thread ID column → INSTANCE
    assert classify_unknown_table("unknown_table", ["thread_id", "data"]) == SyncPolicy.INSTANCE
    
    # Chat ID column → INSTANCE
    assert classify_unknown_table("unknown_table", ["chat_id", "data"]) == SyncPolicy.INSTANCE
    
    # Ran at column → INSTANCE
    assert classify_unknown_table("unknown_table", ["ran_at", "data"]) == SyncPolicy.INSTANCE
    
    # Expires at column → CACHE
    assert classify_unknown_table("unknown_table", ["expires_at", "data"]) == SyncPolicy.CACHE
    
    # Fetched at column → CACHE
    assert classify_unknown_table("unknown_table", ["fetched_at", "data"]) == SyncPolicy.CACHE
    
    # Layer column → SHARED (memory-like)
    assert classify_unknown_table("unknown_table", ["layer", "content"]) == SyncPolicy.SHARED
    
    # Content column → SHARED (memory-like)
    assert classify_unknown_table("unknown_table", ["content", "data"]) == SyncPolicy.SHARED
    
    # Unknown → safe default INSTANCE
    assert classify_unknown_table("unknown_table", ["id", "name"]) == SyncPolicy.INSTANCE


def test_export_includes_only_shared_tables(temp_db):
    """Test that export includes only SHARED tables."""
    sync = DBSync(db_path=temp_db)
    
    # Add test data
    conn = sqlite3.connect(temp_db)
    conn.execute("INSERT INTO memory (key, content, layer) VALUES ('test', 'content', 'technical')")
    conn.execute("INSERT INTO messages (thread_id, role, content) VALUES ('t1', 'user', 'hello')")
    conn.execute("INSERT INTO tool_cache (tool_name, cache_key, data) VALUES ('test_tool', 'key', 'data')")
    conn.commit()
    conn.close()
    
    # Export
    output_path = sync.export_tables(output_path=temp_db.replace(".db", "_export.json"))
    
    # Verify export
    with open(output_path, "r") as f:
        payload = json.load(f)
    
    assert "memory" in payload["data"]
    assert "messages" not in payload["data"]  # INSTANCE table
    assert "tool_cache" not in payload["data"]  # CACHE table
    
    # Cleanup
    os.unlink(output_path)


def test_export_excludes_cache_tables(temp_db):
    """Test that export excludes CACHE tables."""
    sync = DBSync(db_path=temp_db)
    
    # Add test data to cache table
    conn = sqlite3.connect(temp_db)
    conn.execute("INSERT INTO tool_cache (tool_name, cache_key, data) VALUES ('test_tool', 'key', 'data')")
    conn.commit()
    conn.close()
    
    # Export
    output_path = sync.export_tables(output_path=temp_db.replace(".db", "_export.json"))
    
    # Verify cache table excluded
    with open(output_path, "r") as f:
        payload = json.load(f)
    
    assert "tool_cache" not in payload["data"]
    
    # Cleanup
    os.unlink(output_path)


def test_import_dry_run_changes_nothing(temp_db):
    """Test that import with dry_run=True changes nothing."""
    sync = DBSync(db_path=temp_db)
    
    # Create export data
    export_data = {
        "manifest": {
            "timestamp": "2026-05-31T21:00:00",
            "instance": "test",
            "schema_version": "1.0",
            "tables": ["memory"]
        },
        "data": {
            "memory": [
                {"id": 1, "key": "test_key", "content": "test_content", "layer": "technical", 
                 "created": "2026-05-31 21:00:00", "updated": "2026-05-31 21:00:00", "updated_at": "2026-05-31 21:00:00", "active": 1}
            ]
        }
    }
    
    # Write export to file
    export_path = temp_db.replace(".db", "_export.json")
    with open(export_path, "w") as f:
        json.dump(export_data, f)
    
    # Get initial row count
    conn = sqlite3.connect(temp_db)
    initial_count = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
    conn.close()
    
    # Import with dry_run
    report = sync.import_tables(source=export_path, dry_run=True)
    
    # Verify no changes
    conn = sqlite3.connect(temp_db)
    final_count = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
    conn.close()
    
    assert initial_count == final_count
    assert report["added"] == 1  # Reports what would happen
    assert report["updated"] == 0
    
    # Cleanup
    os.unlink(export_path)


def test_import_applies_latest_wins_correctly(temp_db):
    """Test that import applies LATEST_WINS conflict resolution correctly."""
    sync = DBSync(db_path=temp_db)
    
    # Insert existing record
    conn = sqlite3.connect(temp_db)
    conn.execute("""
        INSERT INTO memory (key, content, layer, updated, updated_at)
        VALUES ('test_key', 'old_content', 'technical', '2026-05-30 21:00:00', '2026-05-30 21:00:00')
    """)
    conn.commit()
    conn.close()
    
    # Create export with newer record
    export_data = {
        "manifest": {
            "timestamp": "2026-05-31T21:00:00",
            "instance": "test",
            "schema_version": "1.0",
            "tables": ["memory"]
        },
        "data": {
            "memory": [
                {"id": 1, "key": "test_key", "content": "new_content", "layer": "technical",
                 "created": "2026-05-30 21:00:00", "updated": "2026-05-31 21:00:00", "updated_at": "2026-05-31 21:00:00", "active": 1}
            ]
        }
    }
    
    export_path = temp_db.replace(".db", "_export.json")
    with open(export_path, "w") as f:
        json.dump(export_data, f)
    
    # Import
    report = sync.import_tables(source=export_path, dry_run=False)
    
    # Verify updated
    conn = sqlite3.connect(temp_db)
    row = conn.execute("SELECT content FROM memory WHERE key = 'test_key'").fetchone()
    conn.close()
    
    assert row[0] == "new_content"
    assert report["updated"] == 1
    
    # Cleanup
    os.unlink(export_path)


def test_import_merge_appends_commitments(temp_db):
    """Test that import with MERGE_APPEND strategy appends all records."""
    # Create commitments table
    conn = sqlite3.connect(temp_db)
    conn.execute("""
        CREATE TABLE commitments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            deadline TEXT,
            created DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        INSERT INTO commitments (description, deadline)
        VALUES ('existing commitment', '2026-06-01')
    """)
    conn.commit()
    conn.close()
    
    sync = DBSync(db_path=temp_db)
    
    # Create export with new commitments
    export_data = {
        "manifest": {
            "timestamp": "2026-05-31T21:00:00",
            "instance": "test",
            "schema_version": "1.0",
            "tables": ["commitments"]
        },
        "data": {
            "commitments": [
                {"id": 1, "description": "existing commitment", "deadline": "2026-06-01"},
                {"id": 2, "description": "new commitment 1", "deadline": "2026-06-02"},
                {"id": 3, "description": "new commitment 2", "deadline": "2026-06-03"}
            ]
        }
    }
    
    export_path = temp_db.replace(".db", "_export.json")
    with open(export_path, "w") as f:
        json.dump(export_data, f)
    
    # Import
    report = sync.import_tables(source=export_path, dry_run=False, conflict="merge_append")
    
    # Verify all records added
    conn = sqlite3.connect(temp_db)
    count = conn.execute("SELECT COUNT(*) FROM commitments").fetchone()[0]
    conn.close()
    
    assert count == 3  # All 3 records present
    assert report["added"] == 3
    
    # Cleanup
    os.unlink(export_path)


def test_status_flags_unknown_table(temp_db):
    """Test that status flags unknown tables."""
    sync = DBSync(db_path=temp_db)
    
    # Add an unknown table
    conn = sqlite3.connect(temp_db)
    conn.execute("""
        CREATE TABLE unknown_table_xyz (
            id INTEGER PRIMARY KEY,
            data TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    # Get inventory
    inventory = sync.get_table_inventory()
    
    # Unknown table should be present
    assert "unknown_table_xyz" in inventory
    # Should be auto-classified
    assert inventory["unknown_table_xyz"]["policy"] in ["shared", "instance", "cache", "config"]
