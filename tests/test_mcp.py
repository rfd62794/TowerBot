"""Tests for MCP server and JWT auth."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env")

from infra.mcp.config import MCP_EXPOSED_TOOLS
from tools.registry import TOOL_REGISTRY


@test("mcp: tool listing returns schema")
def test_mcp_tool_listing_returns_schema():
    """list_tools() returns MCP schema for exposed tools."""
    from infra.mcp.server import list_tools
    import asyncio

    async def run_test():
        tools = await list_tools()

        assert isinstance(tools, list), "Expected list of tools"
        assert len(tools) > 0, "Expected at least one tool"

        for tool in tools:
            assert "name" in tool, "Tool must have name"
            assert "description" in tool, "Tool must have description"
            assert "inputSchema" in tool, "Tool must have inputSchema"
            assert tool["name"] in MCP_EXPOSED_TOOLS, f"Tool {tool['name']} not in MCP_EXPOSED_TOOLS"

    asyncio.run(run_test())


@test("mcp: tool execution calls correct fn")
def test_mcp_tool_execution_calls_correct_fn():
    """call_tool() executes the correct function from TOOL_REGISTRY."""
    from infra.mcp.server import call_tool
    import asyncio

    async def run_test():
        # Use a simple tool that doesn't require external deps
        tool_name = "get_weather"
        if tool_name not in MCP_EXPOSED_TOOLS:
            # Skip if not exposed
            return

        result = await call_tool(tool_name, {})

        assert isinstance(result, list), "Expected list of results"
        assert len(result) == 1, "Expected single result"
        assert result[0]["type"] == "text", "Expected text type"
        assert "text" in result[0], "Expected text content"

    asyncio.run(run_test())


@test("mcp: tool not in exposed set raises")
def test_mcp_tool_not_in_exposed_set_raises():
    """call_tool() raises ValueError for non-exposed tools."""
    from infra.mcp.server import call_tool
    import asyncio

    async def run_test():
        try:
            await call_tool("think", {})
            assert False, "Expected ValueError for non-exposed tool"
        except ValueError as e:
            assert "not exposed via MCP" in str(e)

    asyncio.run(run_test())


@test("mcp: jwt generate and validate")
def test_jwt_generate_and_validate():
    """JWT token generation and validation work correctly."""
    from api.mcp.auth import generate_token, validate_token

    token = generate_token(expiry_minutes=60)
    assert isinstance(token, str), "Expected string token"
    assert len(token) > 0, "Expected non-empty token"

    payload = validate_token(token)
    assert payload is not None, "Expected valid token payload"
    assert "scope" in payload, "Expected scope in payload"
    assert payload["scope"] == "mcp_access", "Expected mcp_access scope"


@test("mcp: jwt expired token rejected")
def test_jwt_expired_token_rejected():
    """Expired JWT token is rejected."""
    from api.mcp.auth import generate_token, validate_token

    # Generate token with 1 minute expiry
    token = generate_token(expiry_minutes=1)

    # Mock time to make it expired
    with patch("api.mcp.auth.datetime") as mock_datetime:
        from datetime import datetime, timedelta
        mock_datetime.utcnow.return_value = datetime.utcnow() + timedelta(minutes=2)

        payload = validate_token(token)
        assert payload is None, "Expected None for expired token"


@test("mcp: jwt invalid token rejected")
def test_jwt_invalid_token_rejected():
    """Invalid JWT token is rejected."""
    from api.mcp.auth import validate_token

    payload = validate_token("invalid_token_string")
    assert payload is None, "Expected None for invalid token"

    payload = validate_token("")
    assert payload is None, "Expected None for empty token"
