"""Thinking thread state — shared between transport and agent."""

_current_tool: str | None = None


def set_thinking_tool(tool_name: str | None) -> None:
    """Set the current tool name for thinking thread display."""
    global _current_tool
    _current_tool = tool_name


def get_current_tool() -> str | None:
    """Get the current tool name for thinking thread display."""
    return _current_tool
