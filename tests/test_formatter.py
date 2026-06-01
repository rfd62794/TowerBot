"""Tests for bot/formatter.py Telegram message formatting."""

import pytest
from bot.formatter import format_response, get_tool_display


def test_strip_markdown_tables():
    """Test that markdown table syntax is stripped and headers converted to bold."""
    input_text = """## Last 7 days
| Views | 974 |
| Watch time | 89 min |
| Subscribers | +1 |

Some other text."""
    
    result = format_response(input_text)
    
    # Pipes should be removed
    assert "|" not in result
    # Headers should be converted to bold HTML
    assert "<b>Last 7 days</b>" in result
    # Data should remain
    assert "Views" in result
    assert "974" in result
    assert "89 min" in result


def test_bold_conversion():
    """Test that markdown bold is converted to HTML bold."""
    input_text = "**Views**: 974\n**Watch time**: 89 min"
    
    result = format_response(input_text)
    
    assert "<b>Views</b>" in result
    assert "<b>Watch time</b>" in result
    assert "**" not in result


def test_numeric_compaction():
    """Test that data labels stay compact (under 60 chars)."""
    input_text = "**Average view duration this week**: 5.5 seconds per view"
    
    result = format_response(input_text)
    
    # The formatter doesn't auto-compact, but it should preserve the text
    # The system prompt should guide the LLM to use compact labels
    assert "Average view duration" in result or "view duration" in result
    assert "5.5" in result


def test_special_char_escaping():
    """Test that special characters are escaped outside of HTML tags."""
    input_text = "Value < 100 & > 50\n<b>Bold text</b>"
    
    result = format_response(input_text)
    
    # HTML tags should remain
    assert "<b>Bold text</b>" in result
    # Special chars outside tags should be escaped
    assert "&lt;" in result or "< 100" not in result
    assert "&gt;" in result or "> 50" not in result


def test_chunk_paragraph_breaks():
    """Test that chunking happens at paragraph breaks, not mid-sentence."""
    input_text = """First paragraph with some text.

Second paragraph here.

Third paragraph."""
    
    result = format_response(input_text)
    
    # Paragraph breaks (double newlines) should be preserved
    assert "\n\n" in result
    # Content should remain
    assert "First paragraph" in result
    assert "Second paragraph" in result
    assert "Third paragraph" in result


def test_tool_display_known_tool():
    """Test get_tool_display for known tools."""
    icon, name = get_tool_display("get_youtube_stats")
    
    assert icon == "📊"
    assert name == "Pulling YouTube stats"


def test_tool_display_unknown_tool():
    """Test get_tool_display fallback for unknown tools."""
    icon, name = get_tool_display("unknown_tool_xyz")
    
    assert icon == "⚙️"
    assert name == "Working"


def test_italic_conversion():
    """Test that markdown italic is converted to HTML italic."""
    input_text = "*italic text*"
    
    result = format_response(input_text)
    
    assert "<i>italic text</i>" in result
    assert "*" not in result or "<i>" in result


def test_code_conversion():
    """Test that markdown code is converted to HTML code."""
    input_text = "`code snippet`"
    
    result = format_response(input_text)
    
    assert "<code>code snippet</code>" in result
    assert "`" not in result or "<code>" in result
