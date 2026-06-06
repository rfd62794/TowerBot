"""Tests for content deduplication helpers."""
import pytest
from infra.db import init_db
from infra.db.schema import _conn
from infra.db.content import already_served, mark_served
import sqlite3


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create an in-memory test database before each test."""
    global _conn
    # Close existing connection if any
    if _conn:
        _conn.close()
    
    # Create in-memory database
    _conn = sqlite3.connect(":memory:", check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    
    # Read and execute schema
    with open("infra/db/schema.py") as f:
        content = f.read()
        # Extract SQL between triple quotes
        sql_start = content.find('"""') + 3
        sql_end = content.find('"""', sql_start)
        schema_sql = content[sql_start:sql_end]
        _conn.executescript(schema_sql)
    _conn.commit()
    
    yield
    
    # Cleanup
    if _conn:
        _conn.close()
        _conn = None


def test_already_served_returns_false_for_new_item():
    """Item not in DB → returns False."""
    result = already_served("hackernews", "test123")
    assert result is False


def test_mark_served_inserts_record():
    """After mark_served(), already_served() returns True for same source/id."""
    mark_served("hackernews", "test123", "Test Title", "https://example.com")
    result = already_served("hackernews", "test123")
    assert result is True


def test_already_served_returns_true_after_mark():
    """mark_served("hackernews", "12345", ...) → already_served("hackernews", "12345") == True."""
    mark_served("hackernews", "12345", "HN Post", "https://news.ycombinator.com/item?id=12345")
    assert already_served("hackernews", "12345") is True


def test_mark_served_idempotent():
    """Calling mark_served() twice on same item → no error, still served=1."""
    mark_served("hackernews", "test123", "Title", "https://example.com")
    mark_served("hackernews", "test123", "Title", "https://example.com")  # Should not raise
    assert already_served("hackernews", "test123") is True


def test_different_sources_dont_collide():
    """mark_served("hackernews", "123") → already_served("reddit", "123") still False."""
    mark_served("hackernews", "123", "HN Post", "https://example.com/hn")
    assert already_served("hackernews", "123") is True
    assert already_served("reddit", "123") is False  # Different source, same ID
