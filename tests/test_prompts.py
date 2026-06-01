"""Tests for prompt module dataclasses."""

import sys
import os
import sqlite3
import tempfile
import time

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import pytest
from bot.prompts.monitoring import RedditMonitorPrompt, PyPIMonitorPrompt
from bot.prompts.analysis import MetricSnapshotPrompt
from bot.prompts.content import BlogDraftPrompt
from bot.prompts.delegation import InvestigatePrompt
from tools.meta.delegation import delegation_tools


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
    for _ in range(5):
        try:
            os.unlink(path)
            break
        except PermissionError:
            time.sleep(0.1)


def test_reddit_monitor_render_contains_keywords():
    """Test that RedditMonitorPrompt render includes keywords."""
    prompt = RedditMonitorPrompt(
        keywords=["VoidDrift", "incremental"],
        subreddits=["r/incremental_games", "r/roguelikes"]
    )
    rendered = prompt.render()
    assert "VoidDrift" in rendered
    assert "incremental" in rendered


def test_reddit_monitor_render_contains_subreddits():
    """Test that RedditMonitorPrompt render includes subreddits."""
    prompt = RedditMonitorPrompt(
        keywords=["test"],
        subreddits=["r/incremental_games"]
    )
    rendered = prompt.render()
    assert "r/incremental_games" in rendered


def test_pypi_monitor_render_contains_package():
    """Test that PyPIMonitorPrompt render includes package name."""
    prompt = PyPIMonitorPrompt(
        package="openagent-directive",
        baseline_key="openagent_pypi_baseline"
    )
    rendered = prompt.render()
    assert "openagent-directive" in rendered
    assert "openagent_pypi_baseline" in rendered


def test_metric_snapshot_render_contains_sources():
    """Test that MetricSnapshotPrompt render includes sources."""
    prompt = MetricSnapshotPrompt(
        sources=["youtube", "itch", "pypi"]
    )
    rendered = prompt.render()
    assert "youtube" in rendered
    assert "itch" in rendered
    assert "pypi" in rendered


def test_blog_draft_full_render_contains_rfd_frame():
    """Test that BlogDraftPrompt full draft includes RFD frame."""
    prompt = BlogDraftPrompt(
        topic="building delegation systems",
        voice="RFD Content Frame",
        stage="full_draft"
    )
    rendered = prompt.render()
    assert "RFD Content Frame" in rendered
    assert "MOMENT" in rendered
    assert "SURPRISE" in rendered
    assert "STRUGGLE" in rendered
    assert "LESSON" in rendered
    assert "NEXT" in rendered


def test_blog_draft_skeleton_render_mentions_create_draft():
    """Test that BlogDraftPrompt skeleton mentions create_blog_draft."""
    prompt = BlogDraftPrompt(
        topic="building delegation systems",
        stage="skeleton"
    )
    rendered = prompt.render()
    assert "create_blog_draft" in rendered


def test_investigate_render_contains_question():
    """Test that InvestigatePrompt render includes the question."""
    prompt = InvestigatePrompt(
        question="What is the current state of the delegation system?",
        return_format="summary"
    )
    rendered = prompt.render()
    assert "current state of the delegation system" in rendered


def test_queue_task_accepts_prompt_object(temp_db):
    """Test that queue_task accepts BasePrompt instances."""
    prompt = InvestigatePrompt(
        question="Test question",
        return_format="bullets"
    )
    result = delegation_tools.queue_task(prompt)
    assert result["ok"] is True
    assert "task_id" in result
    assert result["status"] == "queued"
