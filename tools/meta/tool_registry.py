"""
Tool discovery and dynamic registration.
a2asearch integration + OpenAPI spec → PrivyBot tool generation.
Experimental tools: registered immediately, promoted explicitly.
"""
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

A2A_SEARCH_URL = "https://api.a2asearch.com/v1/search"
A2A_FALLBACK_URL = "https://a2asearch.com/api/search"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────
# TOOL DISCOVERY
# ─────────────────────────────────────────────

def a2a_search(query: str, limit: int = 10) -> dict:
    """
    Search a2asearch.com index for MCP tools and skills.
    Returns matching tools with name, description, install command.

    PARAMS:
      query: search terms (e.g. 'weather forecast', 'github issues')
      limit: max results (default 10, max 25)

    RETURNS: dict with ok, count, results (list with name, description,
             source, install_command, tags)
    """
    limit = min(max(1, limit), 25)

    try:
        response = httpx.get(
            A2A_SEARCH_URL,
            params={"q": query, "limit": limit},
            timeout=10.0,
            headers={"User-Agent": "PrivyBot/1.0 tool-discovery"}
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("results", data if isinstance(data, list) else []):
            results.append({
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "source": item.get("source", item.get("url", "")),
                "install_command": item.get("install", item.get("command", "")),
                "tags": item.get("tags", [])
            })

        return {"ok": True, "count": len(results), "results": results,
                "query": query}

    except httpx.HTTPStatusError as e:
        # Try fallback URL
        try:
            response = httpx.get(
                A2A_FALLBACK_URL,
                params={"q": query, "limit": limit},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return {"ok": True, "count": len(data), "results": data,
                    "query": query, "via": "fallback"}
        except Exception:
            return {"ok": False, "error": str(e), "query": query}

    except Exception as e:
        return {"ok": False, "error": str(e), "query": query}


# ─────────────────────────────────────────────
# DYNAMIC TOOL REGISTRATION
# ─────────────────────────────────────────────

def register_tool_from_spec(spec_url: str,
                             tool_prefix: str = "",
                             max_tools: int = 5) -> dict:
    """
    Fetch an OpenAPI spec URL, generate PrivyBot tool definitions,
    and register them to the experimental_tools table.

    Each generated tool:
    - Has a name prefixed with tool_prefix if provided
    - Is registered as 'experimental' status
    - Sends a Telegram notification on registration
    - Is callable immediately via experimental registry

    PARAMS:
      spec_url: URL to OpenAPI/Swagger JSON spec
      tool_prefix: optional prefix for generated tool names
      max_tools: max tools to generate from spec (default 5, max 20)

    RETURNS: dict with ok, registered (list of tool names), skipped,
             errors
    """
    max_tools = min(max(1, max_tools), 20)

    # Fetch spec
    try:
        response = httpx.get(spec_url, timeout=15.0,
                             follow_redirects=True)
        response.raise_for_status()
        spec = response.json()
    except Exception as e:
        return {"ok": False, "error": f"Failed to fetch spec: {e}",
                "spec_url": spec_url}

    # Extract tools from spec
    tools = _generate_tools_from_spec(spec, tool_prefix, max_tools)

    if not tools:
        return {"ok": False, "error": "No usable endpoints found in spec",
                "spec_url": spec_url}

    # Register each tool
    registered = []
    skipped = []
    errors = []

    from infra.db.schema import _exec

    for tool in tools:
        try:
            existing = _exec(
                "SELECT id FROM experimental_tools WHERE name=?",
                (tool["name"],)
            )
            if existing:
                skipped.append(tool["name"])
                continue

            _exec(
                """INSERT INTO experimental_tools
                   (id, name, description, source_type, source_url,
                    input_schema, status, created_at)
                   VALUES (?, ?, ?, 'openapi', ?, ?, 'experimental', ?)""",
                (_uuid(), tool["name"], tool["description"],
                 spec_url, json.dumps(tool["input_schema"]), _now()),
                commit=True
            )
            registered.append(tool["name"])
            logger.info(f"Registered experimental tool: {tool['name']}")

        except Exception as e:
            errors.append({"name": tool["name"], "error": str(e)})

    return {
        "ok": True,
        "spec_url": spec_url,
        "registered": registered,
        "skipped": skipped,
        "errors": errors,
        "message": (
            f"Registered {len(registered)} experimental tools. "
            f"Call promote_tool(name) to promote after verification."
        )
    }


def _generate_tools_from_spec(spec: dict, prefix: str,
                               max_tools: int) -> list[dict]:
    """
    Extract endpoint definitions from an OpenAPI spec.
    Returns list of tool dicts with name, description, input_schema.
    """
    tools = []
    paths = spec.get("paths", {})
    info = spec.get("info", {})
    api_title = info.get("title", "api").lower().replace(" ", "_")

    for path, methods in paths.items():
        if len(tools) >= max_tools:
            break

        for method, operation in methods.items():
            if method not in ("get", "post") or len(tools) >= max_tools:
                continue

            op_id = operation.get("operationId", "")
            summary = operation.get("summary", operation.get("description", ""))
            if not summary:
                continue

            # Build tool name
            if op_id:
                raw_name = op_id.replace("-", "_").replace(" ", "_")
            else:
                clean_path = path.strip("/").replace("/", "_").replace(
                    "{", "").replace("}", "")
                raw_name = f"{method}_{clean_path}"

            name = f"{prefix}_{raw_name}" if prefix else raw_name
            name = name[:60]  # max name length

            # Build input schema from parameters
            properties = {}
            required = []

            for param in operation.get("parameters", []):
                if param.get("in") in ("query", "path"):
                    pname = param["name"]
                    pschema = param.get("schema", {})
                    properties[pname] = {
                        "type": pschema.get("type", "string"),
                        "description": param.get("description", "")
                    }
                    if param.get("required", False):
                        required.append(pname)

            tools.append({
                "name": name,
                "description": f"{summary} ({method.upper()} {path})",
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            })

    return tools


# ─────────────────────────────────────────────
# EXPERIMENTAL REGISTRY MANAGEMENT
# ─────────────────────────────────────────────

def list_experimental_tools(status: str = None) -> dict:
    """
    List dynamically registered tools with their status.
    status: 'experimental' | 'promoted' | 'failed' | None (all)

    RETURNS: dict with ok, count, tools (list with name, description,
             status, use_count, error_count, created_at)
    """
    from infra.db.schema import _exec
    try:
        if status:
            rows = _exec(
                """SELECT name, description, status, source_type,
                          source_url, use_count, error_count, created_at,
                          promoted_at
                   FROM experimental_tools WHERE status=?
                   ORDER BY created_at DESC""",
                (status,)
            )
        else:
            rows = _exec(
                """SELECT name, description, status, source_type,
                          source_url, use_count, error_count, created_at,
                          promoted_at
                   FROM experimental_tools
                   ORDER BY created_at DESC"""
            )
        tools = [dict(r) for r in (rows or [])]
        return {"ok": True, "count": len(tools), "tools": tools}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def promote_tool(name: str) -> dict:
    """
    Promote an experimental tool to promoted status.
    Explicit call required — never auto-promotes.
    Sends notification on promotion.

    RETURNS: dict with ok, name, previous_status, promoted_at
    """
    from infra.db.schema import _exec
    try:
        rows = _exec(
            "SELECT * FROM experimental_tools WHERE name=?",
            (name,)
        ).fetchone()
        if not rows:
            return {"ok": False, "error": f"Tool not found: {name}"}

        task = dict(rows)
        if task["status"] == "promoted":
            return {"ok": False, "error": f"Tool already promoted: {name}"}

        now = _now()
        _exec(
            """UPDATE experimental_tools
               SET status='promoted', promoted_at=? WHERE name=?""",
            (now, name),
            commit=True
        )

        logger.info(f"Tool promoted: {name}")
        return {
            "ok": True,
            "name": name,
            "previous_status": task["status"],
            "promoted_at": now,
            "message": f"Tool '{name}' promoted to main registry."
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
