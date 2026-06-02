"""Tests for tool discovery and dynamic registration."""

import json
from unittest.mock import patch, MagicMock

import pytest

from tools.meta.tool_registry import (
    a2a_search,
    register_tool_from_spec,
    _generate_tools_from_spec,
    list_experimental_tools,
    promote_tool,
)


@pytest.fixture()
def test_db():
    """Initialize test database with experimental_tools table."""
    from infra.db import schema
    schema.init_db(":memory:")
    yield schema._conn
    if schema._conn:
        schema._conn.close()


def run_all():
    """Shim for verify.py compatibility."""
    pytest.main([__file__, "-v"]])


# ─────────────────────────────────────────────
# TABLE EXISTS
# ─────────────────────────────────────────────

def test_experimental_tools_table_exists(test_db):
    """Table created by init_db — all columns present."""
    from infra.db.schema import _exec
    cols = {row[1] for row in _exec("PRAGMA table_info(experimental_tools)").fetchall()}
    expected = {
        "id", "name", "description", "source_type", "source_url",
        "input_schema", "handler_code", "status", "use_count",
        "error_count", "created_at", "promoted_at", "last_used_at", "notes"
    }
    assert cols == expected


# ─────────────────────────────────────────────
# A2A SEARCH
# ─────────────────────────────────────────────

@patch("tools.meta.tool_registry.httpx.get")
def test_a2a_search_success(mock_get):
    """Mock httpx returns results — ok=True, count matches."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"name": "weather_tool", "description": "Get weather", "source": "github.com/weather", "install": "pip install weather", "tags": ["weather"]},
            {"name": "github_issues", "description": "Search GitHub issues", "source": "github.com/issues", "install": "pip install gh", "tags": ["github"]},
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = a2a_search("weather", limit=5)
    assert result["ok"] is True
    assert result["count"] == 2
    assert len(result["results"]) == 2
    assert result["query"] == "weather"


@patch("tools.meta.tool_registry.httpx.get")
def test_a2a_search_fallback(mock_get):
    """Primary fails, fallback succeeds — ok=True, via='fallback'."""
    # Primary fails
    primary_response = MagicMock()
    primary_response.raise_for_status.side_effect = Exception("Primary failed")
    
    # Fallback succeeds
    fallback_response = MagicMock()
    fallback_response.json.return_value = [
        {"name": "test_tool", "description": "Test", "source": "test.com", "install": "npm install test", "tags": []}
    ]
    fallback_response.raise_for_status = MagicMock()
    
    mock_get.side_effect = [primary_response, fallback_response]

    result = a2a_search("test")
    assert result["ok"] is True
    assert result["via"] == "fallback"


@patch("tools.meta.tool_registry.httpx.get")
def test_a2a_search_both_fail(mock_get):
    """Both URLs fail — ok=False, error present."""
    mock_get.side_effect = [Exception("Primary failed"), Exception("Fallback failed")]

    result = a2a_search("test")
    assert result["ok"] is False
    assert "error" in result


@patch("tools.meta.tool_registry.httpx.get")
def test_a2a_search_limit_capped(mock_get):
    """limit=100 passed — capped to 25 in request."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    a2a_search("test", limit=100)
    mock_get.assert_called()
    # Check that limit was capped to 25 in the params
    call_args = mock_get.call_args
    assert call_args[1]["params"]["limit"] == 25


# ─────────────────────────────────────────────
# REGISTER TOOL FROM SPEC
# ─────────────────────────────────────────────

@patch("tools.meta.tool_registry.httpx.get")
def test_register_tool_from_spec_valid(mock_get, test_db):
    """Mock spec with 2 endpoints — 2 tools registered."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "paths": {
            "/weather": {
                "get": {
                    "operationId": "getWeather",
                    "summary": "Get current weather",
                    "parameters": [
                        {"name": "city", "in": "query", "schema": {"type": "string"}, "required": True}
                    ]
                }
            },
            "/forecast": {
                "post": {
                    "operationId": "getForecast",
                    "summary": "Get weather forecast",
                    "parameters": []
                }
            }
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = register_tool_from_spec("https://example.com/openapi.json", max_tools=5)
    assert result["ok"] is True
    assert len(result["registered"]) == 2
    assert "getWeather" in result["registered"] or "get_weather" in result["registered"]


@patch("tools.meta.tool_registry.httpx.get")
def test_register_tool_from_spec_bad_url(mock_get):
    """HTTP error fetching spec — ok=False."""
    mock_get.side_effect = Exception("HTTP 404")

    result = register_tool_from_spec("https://example.com/bad.json")
    assert result["ok"] is False
    assert "Failed to fetch spec" in result["error"]


@patch("tools.meta.tool_registry.httpx.get")
def test_register_tool_from_spec_empty_spec(mock_get):
    """Spec with no paths — ok=False."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"paths": {}}
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = register_tool_from_spec("https://example.com/empty.json")
    assert result["ok"] is False
    assert "No usable endpoints" in result["error"]


@patch("tools.meta.tool_registry.httpx.get")
def test_register_tool_from_spec_deduplication(mock_get, test_db):
    """Same tool registered twice — second skipped."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "paths": {
            "/test": {
                "get": {
                    "operationId": "testTool",
                    "summary": "Test tool",
                    "parameters": []
                }
            }
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    # First registration
    result1 = register_tool_from_spec("https://example.com/spec.json")
    assert result1["ok"] is True
    assert len(result1["registered"]) == 1

    # Second registration (should skip)
    result2 = register_tool_from_spec("https://example.com/spec.json")
    assert result2["ok"] is True
    assert len(result2["registered"]) == 0
    assert len(result2["skipped"]) == 1


@patch("tools.meta.tool_registry.httpx.get")
def test_register_tool_prefix(mock_get, test_db):
    """tool_prefix='myapi' — names start with 'myapi_'."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "paths": {
            "/test": {
                "get": {
                    "operationId": "testTool",
                    "summary": "Test tool",
                    "parameters": []
                }
            }
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = register_tool_from_spec("https://example.com/spec.json", tool_prefix="myapi")
    assert result["ok"] is True
    assert len(result["registered"]) == 1
    assert result["registered"][0].startswith("myapi_")


@patch("tools.meta.tool_registry.httpx.get")
def test_register_tool_max_tools_cap(mock_get, test_db):
    """Spec with 10 endpoints, max_tools=3 — only 3 registered."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "paths": {
            f"/endpoint{i}": {
                "get": {
                    "operationId": f"tool{i}",
                    "summary": f"Tool {i}",
                    "parameters": []
                }
            }
            for i in range(10)
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = register_tool_from_spec("https://example.com/spec.json", max_tools=3)
    assert result["ok"] is True
    assert len(result["registered"]) == 3


# ─────────────────────────────────────────────
# GENERATE TOOLS FROM SPEC
# ─────────────────────────────────────────────

def test_generate_tools_from_spec_get():
    """GET endpoint generates tool with path params."""
    spec = {
        "paths": {
            "/users/{id}": {
                "get": {
                    "operationId": "getUser",
                    "summary": "Get user by ID",
                    "parameters": [
                        {"name": "id", "in": "path", "schema": {"type": "string"}, "required": True}
                    ]
                }
            }
        }
    }
    tools = _generate_tools_from_spec(spec, "", 10)
    assert len(tools) == 1
    assert tools[0]["name"] == "getUser"
    assert "id" in tools[0]["input_schema"]["properties"]
    assert "id" in tools[0]["input_schema"]["required"]


def test_generate_tools_from_spec_post():
    """POST endpoint generates tool."""
    spec = {
        "paths": {
            "/users": {
                "post": {
                    "operationId": "createUser",
                    "summary": "Create a new user",
                    "parameters": []
                }
            }
        }
    }
    tools = _generate_tools_from_spec(spec, "", 10)
    assert len(tools) == 1
    assert tools[0]["name"] == "createUser"


def test_generate_tools_skips_other_methods():
    """PUT/DELETE endpoints — not in results."""
    spec = {
        "paths": {
            "/users/{id}": {
                "put": {
                    "operationId": "updateUser",
                    "summary": "Update user",
                    "parameters": []
                },
                "delete": {
                    "operationId": "deleteUser",
                    "summary": "Delete user",
                    "parameters": []
                }
            }
        }
    }
    tools = _generate_tools_from_spec(spec, "", 10)
    assert len(tools) == 0


# ─────────────────────────────────────────────
# LIST EXPERIMENTAL TOOLS
# ─────────────────────────────────────────────

def test_list_experimental_tools_all(test_db):
    """Returns all registered tools."""
    from infra.db.schema import _exec
    _exec(
        """INSERT INTO experimental_tools (id, name, description, source_type, source_url, input_schema, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("test-id-1", "test_tool", "Test tool", "openapi", "https://example.com", "{}", "experimental", "2024-01-01T00:00:00Z"),
        commit=True
    )

    result = list_experimental_tools()
    assert result["ok"] is True
    assert result["count"] >= 1
    assert any(t["name"] == "test_tool" for t in result["tools"])


def test_list_experimental_tools_filtered(test_db):
    """status='promoted' — only promoted tools."""
    from infra.db.schema import _exec
    _exec(
        """INSERT INTO experimental_tools (id, name, description, source_type, source_url, input_schema, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("test-id-2", "exp_tool", "Experimental", "openapi", "https://example.com", "{}", "experimental", "2024-01-01T00:00:00Z"),
        commit=True
    )
    _exec(
        """INSERT INTO experimental_tools (id, name, description, source_type, source_url, input_schema, status, created_at, promoted_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("test-id-3", "promoted_tool", "Promoted", "openapi", "https://example.com", "{}", "promoted", "2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"),
        commit=True
    )

    result = list_experimental_tools(status="promoted")
    assert result["ok"] is True
    assert all(t["status"] == "promoted" for t in result["tools"])


# ─────────────────────────────────────────────
# PROMOTE TOOL
# ─────────────────────────────────────────────

def test_promote_tool_success(test_db):
    """Experimental tool — status becomes promoted."""
    from infra.db.schema import _exec
    _exec(
        """INSERT INTO experimental_tools (id, name, description, source_type, source_url, input_schema, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("test-id-4", "to_promote", "Tool to promote", "openapi", "https://example.com", "{}", "experimental", "2024-01-01T00:00:00Z"),
        commit=True
    )

    result = promote_tool("to_promote")
    assert result["ok"] is True
    assert result["name"] == "to_promote"
    assert result["previous_status"] == "experimental"
    assert "promoted_at" in result


def test_promote_tool_already_promoted(test_db):
    """Already promoted — ok=False."""
    from infra.db.schema import _exec
    _exec(
        """INSERT INTO experimental_tools (id, name, description, source_type, source_url, input_schema, status, created_at, promoted_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("test-id-5", "already_promoted", "Already promoted", "openapi", "https://example.com", "{}", "promoted", "2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"),
        commit=True
    )

    result = promote_tool("already_promoted")
    assert result["ok"] is False
    assert "already promoted" in result["error"]
