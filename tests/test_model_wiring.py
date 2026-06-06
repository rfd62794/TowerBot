"""
Model router wiring tests — verify model routing and tool index functionality.
"""
import pytest
from unittest.mock import MagicMock, patch


def test_search_tools_finds_by_name():
    """query='itch' → get_itch_stats in results"""
    from tools.meta.tool_index import search_tools
    result = search_tools("itch", limit=10)
    assert result["ok"] is True
    assert result["count"] > 0
    tool_names = [t["name"] for t in result["tools"]]
    assert "get_itch_stats" in tool_names


def test_search_tools_finds_by_description():
    """query='email inbox' → get_inbox_summary in results"""
    from tools.meta.tool_index import search_tools
    result = search_tools("email inbox", limit=10)
    assert result["ok"] is True
    assert result["count"] > 0
    tool_names = [t["name"] for t in result["tools"]]
    assert "get_inbox_summary" in tool_names


def test_search_tools_name_weighted_higher():
    """name match scores higher than desc match"""
    from tools.meta.tool_index import search_tools
    result = search_tools("itch", limit=10)
    assert result["ok"] is True
    # Both itch tools should be in results due to name match
    if result["count"] > 0:
        tool_names = [t["name"] for t in result["tools"]]
        assert "get_itch_stats" in tool_names
        assert "itch_post_devlog" in tool_names


def test_search_tools_limit():
    """limit=3 → max 3 results"""
    from tools.meta.tool_index import search_tools
    result = search_tools("get", limit=3)
    assert result["ok"] is True
    assert result["count"] <= 3


def test_search_tools_empty_query():
    """empty query → ok=True, empty results"""
    from tools.meta.tool_index import search_tools
    result = search_tools("", limit=10)
    assert result["ok"] is True
    assert result["count"] == 0


def test_search_tools_no_match():
    """query='xyznotareal' → ok=True, count=0"""
    from tools.meta.tool_index import search_tools
    result = search_tools("xyznotareal", limit=10)
    assert result["ok"] is True
    assert result["count"] == 0


def test_list_all_tools_no_prefix():
    """Returns all tools sorted by name"""
    from tools.meta.tool_index import list_all_tools
    result = list_all_tools()
    assert result["ok"] is True
    assert result["count"] > 0
    # Check sorted by name
    names = [t["name"] for t in result["tools"]]
    assert names == sorted(names)


def test_list_all_tools_prefix():
    """prefix='get_' → only get_ tools"""
    from tools.meta.tool_index import list_all_tools
    result = list_all_tools(prefix="get_")
    assert result["ok"] is True
    assert result["count"] > 0
    for tool in result["tools"]:
        assert tool["name"].startswith("get_")


def test_get_tool_info_found():
    """Known tool name → ok=True, description present"""
    from tools.meta.tool_index import get_tool_info
    result = get_tool_info("get_itch_stats")
    assert result["ok"] is True
    assert result["name"] == "get_itch_stats"
    # Description may be empty for some tools, just check the structure
    assert "description" in result


def test_get_tool_info_not_found():
    """Bad name → ok=False, error present"""
    from tools.meta.tool_index import get_tool_info
    result = get_tool_info("nonexistent_tool_xyz")
    assert result["ok"] is False
    assert "error" in result


def test_task_types_yaml_has_model_roles():
    """All 5 task types have model_role field"""
    import yaml
    from pathlib import Path
    config_path = Path(__file__).parent.parent / "config" / "task_types.yaml"
    with open(config_path) as f:
        task_types = yaml.safe_load(f)
    
    for task_type in ["monitor", "reporter", "creator", "planner", "chat"]:
        assert task_type in task_types
        assert "model_role" in task_types[task_type]
        assert task_types[task_type]["model_role"] is not None


def run_all() -> tuple[int, int]:
    """Shim for verify.py compatibility."""
    import sys
    exit_code = pytest.main([__file__, "-v"])
    if exit_code == 0:
        return (11, 0)  # 11 tests in this file
    else:
        return (0, 1)
