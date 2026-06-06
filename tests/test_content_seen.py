"""Tests for content deduplication helpers."""
import pytest
from infra.db.schema import init_db, DB_PATH
from infra.db.content import already_served, mark_served
import os
import tempfile


@pytest.fixture
def test_db():
    """Create an in-memory test database."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(db_path)
    yield db_path
    os.unlink(db_path)


def test_already_served_returns_false_for_new_item(test_db):
    """Item not in DB → returns False."""
    # Override DB_PATH for this test
    import infra.db.schema
    original_db = infra.db.schema.DB_PATH
    infra.db.schema.DB_PATH = test_db
    infra.db.schema.init_db(test_db)
    
    result = already_served("hackernews", "test123")
    assert result is False
    
    # Restore original
    infra.db.schema.DB_PATH = original_db


def test_mark_served_inserts_record(test_db):
    """After mark_served(), already_served() returns True for same source/id."""
    import infra.db.schema
    original_db = infra.db.schema.DB_PATH
    infra.db.schema.DB_PATH = test_db
    infra.db.schema.init_db(test_db)
    
    mark_served("hackernews", "test123", "Test Title", "https://example.com")
    result = already_served("hackernews", "test123")
    assert result is True
    
    infra.db.schema.DB_PATH = original_db


def test_already_served_returns_true_after_mark(test_db):
    """mark_served("hackernews", "12345", ...) → already_served("hackernews", "12345") == True."""
    import infra.db.schema
    original_db = infra.db.schema.DB_PATH
    infra.db.schema.DB_PATH = test_db
    infra.db.schema.init_db(test_db)
    
    mark_served("hackernews", "12345", "HN Post", "https://news.ycombinator.com/item?id=12345")
    assert already_served("hackernews", "12345") is True
    
    infra.db.schema.DB_PATH = original_db


def test_mark_served_idempotent(test_db):
    """Calling mark_served() twice on same item → no error, still served=1."""
    import infra.db.schema
    original_db = infra.db.schema.DB_PATH
    infra.db.schema.DB_PATH = test_db
    infra.db.schema.init_db(test_db)
    
    mark_served("hackernews", "test123", "Title", "https://example.com")
    mark_served("hackernews", "test123", "Title", "https://example.com")  # Should not raise
    assert already_served("hackernews", "test123") is True
    
    infra.db.schema.DB_PATH = original_db


def test_different_sources_dont_collide(test_db):
    """mark_served("hackernews", "123") → already_served("reddit", "123") still False."""
    import infra.db.schema
    original_db = infra.db.schema.DB_PATH
    infra.db.schema.DB_PATH = test_db
    infra.db.schema.init_db(test_db)
    
    mark_served("hackernews", "123", "HN Post", "https://example.com/hn")
    assert already_served("hackernews", "123") is True
    assert already_served("reddit", "123") is False  # Different source, same ID
    
    infra.db.schema.DB_PATH = original_db
