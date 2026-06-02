"""
Tool index — fast searchable catalog of all registered tools.
Enables the agent to find tools at runtime without hardcoded routes.
"""
import logging
from typing import Any
logger = logging.getLogger(__name__)


def _get_all_tools() -> list[dict]:
    """Load all tools from TOOL_REGISTRY with their descriptions."""
    try:
        from tools.registry import TOOL_REGISTRY
        tools = []
        for name, definition in TOOL_REGISTRY.items():
            desc = ""
            if isinstance(definition, dict):
                desc = definition.get("description", "")
            elif hasattr(definition, "__doc__") and definition.__doc__:
                desc = definition.__doc__.strip().split("\n")[0]
            tools.append({
                "name": name,
                "description": desc
            })
        return tools
    except Exception as e:
        logger.error(f"Failed to load tool registry: {e}")
        return []


def search_tools(query: str, limit: int = 10) -> dict:
    """
    Search all registered tools by name and description.
    Fast fuzzy match — finds relevant tools for any task description.
    Use this when you need a tool but aren't sure of the exact name.

    PARAMS:
      query: what you want to do (e.g. 'send email', 'get itch stats',
             'search reddit', 'check calendar')
      limit: max results (default 10)

    RETURNS: dict with ok, count, tools (list with name, description,
             relevance_score)
    """
    limit = min(max(1, limit), 25)
    query_lower = query.lower()
    query_terms = query_lower.split()

    all_tools = _get_all_tools()
    scored = []

    for tool in all_tools:
        name_lower = tool["name"].lower()
        desc_lower = tool["description"].lower()
        combined = f"{name_lower} {desc_lower}"

        score = 0
        for term in query_terms:
            if term in name_lower:
                score += 3        # name match weighted higher
            if term in desc_lower:
                score += 1        # description match
            if name_lower.startswith(term):
                score += 2        # prefix match bonus

        if score > 0:
            scored.append({
                "name": tool["name"],
                "description": tool["description"][:120],
                "relevance_score": score
            })

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    results = scored[:limit]

    return {
        "ok": True,
        "query": query,
        "count": len(results),
        "tools": results,
        "total_tools": len(all_tools)
    }


def list_all_tools(prefix: str = None) -> dict:
    """
    List all registered tools, optionally filtered by name prefix.
    Use to browse available capabilities by category.

    PARAMS:
      prefix: optional name prefix filter (e.g. 'get_', 'search_',
              'youtube_', 'blog_')

    RETURNS: dict with ok, count, tools (list with name, description)
    """
    all_tools = _get_all_tools()

    if prefix:
        prefix_lower = prefix.lower()
        all_tools = [t for t in all_tools
                     if t["name"].lower().startswith(prefix_lower)]

    tools = [
        {"name": t["name"], "description": t["description"][:120]}
        for t in sorted(all_tools, key=lambda x: x["name"])
    ]

    return {
        "ok": True,
        "count": len(tools),
        "tools": tools,
        "prefix": prefix
    }


def get_tool_info(name: str) -> dict:
    """
    Get full information about a specific tool by exact name.

    RETURNS: dict with ok, name, description, parameters (if available)
    """
    try:
        from tools.registry import TOOL_REGISTRY
        if name not in TOOL_REGISTRY:
            return {"ok": False, "error": f"Tool not found: {name}"}

        definition = TOOL_REGISTRY[name]
        desc = ""
        params = {}

        if isinstance(definition, dict):
            desc = definition.get("description", "")
            params = definition.get("parameters", {})
        elif callable(definition):
            desc = (definition.__doc__ or "").strip()

        return {
            "ok": True,
            "name": name,
            "description": desc,
            "parameters": params
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
