"""Utility functions for common patterns across PrivyBot.

This module consolidates recurring patterns to eliminate duplication
and prevent the class of bug where the same fix must be applied in
multiple places.
"""

import json
from typing import Any


def safe_serialize(result: Any) -> str:
    """Safely convert any result to a string for database storage.
    
    Handles strings, JSON-serializable objects, and fallback to str().
    This prevents serialization errors when task results are stored
    in agent_actions or other database tables.
    
    Args:
        result: Any result from a task or tool call
        
    Returns:
        String representation suitable for database storage
    """
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result)
    except (TypeError, ValueError):
        return str(result)


def get_task_type(task_name: str) -> str:
    """Map task name to prompt type for base prompt injection.
    
    Args:
        task_name: Name of the task from config/tasks.yaml
        
    Returns:
        Prompt type key for infra/prompts.py mapping
    """
    # Map task names to prompt types
    task_to_type = {
        # Briefing
        "morning_briefing": "briefing",
        "mid_day_checkin": "briefing",
        "bedtime_summary": "briefing",
        
        # Content
        "content_decision_prompt": "content",
        "content_gap_detector": "content",
        "blog_structure_generator": "content",
        
        # Research
        "research_request": "research",
        "tech_digest": "research",
        "daily_finds": "research",
        
        # Monitoring
        "hn_monitor": "monitoring",
        "community_opportunity_scout": "monitoring",
        "opportunity_capture": "monitoring",
        
        # Planning
        "debt_followup": "planning",
        "weekly_accountability": "planning",
        "self_expansion_planner": "planner",
        
        # Skill review
        "skill_review": "skill_review",
        
        # Default fallback
    }
    
    return task_to_type.get(task_name, "default")


def already_served(content_key: str) -> bool:
    """Check if content has already been served to avoid duplicates.
    
    Wrapper around infra.db.content.check_content_seen for convenience.
    
    Args:
        content_key: Unique identifier for the content
        
    Returns:
        True if content was already served, False otherwise
    """
    from infra.db.content import check_content_seen
    return check_content_seen(content_key)


def mark_served(content_key: str) -> None:
    """Mark content as served to prevent future duplicates.
    
    Wrapper around infra.db.content.mark_content_seen for convenience.
    
    Args:
        content_key: Unique identifier for the content
    """
    from infra.db.content import mark_content_seen
    mark_content_seen(content_key)


async def notify(message: str, send_fn, urgent: bool = False) -> None:
    """Send immediate Telegram notification from autonomous task.
    
    Args:
        message: Notification message to send
        send_fn: Async send function for Telegram
        urgent: Whether to prefix with urgent emoji
    """
    try:
        prefix = "🔴 " if urgent else "💡 "
        await send_fn(f"{prefix}{message}")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[notification] failed: {e}")
