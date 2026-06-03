"""Tests for tools/productivity/utils.py parsing functions."""

import pytest
from tools.productivity.utils import parse_natural_deadline, parse_recurrence


def test_parse_natural_deadline_today():
    """parse_natural_deadline parses 'today' correctly."""
    result = parse_natural_deadline("today")
    assert result is not None
    assert "date" in result
    assert "time" in result


def test_parse_natural_deadline_tomorrow():
    """parse_natural_deadline parses 'tomorrow' correctly."""
    result = parse_natural_deadline("tomorrow")
    assert result is not None
    assert "date" in result
    assert "time" in result


def test_parse_natural_deadline_friday():
    """parse_natural_deadline parses day names correctly."""
    result = parse_natural_deadline("Friday")
    assert result is not None
    assert "date" in result


def test_parse_natural_deadline_with_time():
    """parse_natural_deadline parses 'tomorrow at 5pm' correctly."""
    result = parse_natural_deadline("tomorrow at 5pm")
    assert result is not None
    assert "date" in result
    assert "time" in result


def test_parse_natural_deadline_invalid():
    """parse_natural_deadline returns None for invalid input."""
    result = parse_natural_deadline("gibberish")
    # Should handle gracefully - either None or empty dict
    assert result is None or result == {}


def test_parse_recurrence_daily():
    """parse_recurrence parses 'every day' correctly."""
    result = parse_recurrence("every day")
    assert result is not None
    assert "daily" in result.lower() or "day" in result.lower()


def test_parse_recurrence_weekly():
    """parse_recurrence parses 'every Monday' correctly."""
    result = parse_recurrence("every Monday")
    assert result is not None
    assert "monday" in result.lower()


def test_parse_recurrence_none():
    """parse_recurrence returns None for non-recurrence input."""
    result = parse_recurrence("just once")
    assert result is None
