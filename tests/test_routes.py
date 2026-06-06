"""Coverage invariant: every tool in TOOL_REGISTRY must appear in at least one route.

Fails immediately when a tool is added to the registry without a route assignment.
Cannot be skipped without explicit justification (ADR-036).
"""

import os
import sys
import yaml

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from tools.registry import TOOL_REGISTRY

# Internal/admin tools that don't need route assignments
# These are MCP-only, experimental, or backend tools not exposed to user-facing routes
ROUTE_EXEMPT = {
    # Delegation tools (MCP-only)
    "queue_task", "cancel_task", "get_task_result", "list_pending_tasks",
    # Shell tools (MCP-only)
    "run_named_command", "execute_shell", "list_named_commands",
    # Chain tools (experimental)
    "get_chain", "get_chains", "get_chain_payload", "start_chain", "resume_chain", "cancel_chain",
    # Admin tools (MCP-only)
    "run_diagnostic", "get_logs", "query_db", "search_tools",
    # Experimental tools
    "list_experimental_tools", "promote_tool", "delete_experimental_template",
    # Template tools (MCP-only)
    "get_template", "list_templates", "write_template",
    # WordPress tools (MCP-only)
    "create_page", "delete_page", "get_page", "get_pages", "update_page",
    # Google Tasks tools (MCP-only)
    "create_google_task", "delete_google_task", "get_google_task", "list_google_tasks", "update_google_task", "sync_google_tasks", "complete_google_task",
    # Memory tools (MCP-only)
    "delete_memory", "list_memories",
    # Post pipeline tools (MCP-only)
    "advance_post_pipeline", "create_draft_from_pipeline", "get_post_pipeline_state", "get_promotion_candidates",
    # Misc internal tools
    "a2a_search", "purge_null_tasks", "register_tool_from_spec", "get_tool_info", "list_all_tools",
}


def _load_routes() -> dict:
    path = os.path.join(_root, "config", "routes.yaml")
    with open(path) as f:
        return yaml.safe_load(f)["routes"]


def test_all_registry_tools_have_a_route():
    """Every key in TOOL_REGISTRY must appear in at least one route's tool list."""
    routes = _load_routes()
    routed_tools: set[str] = set()
    for route in routes.values():
        routed_tools.update(route.get("tools") or [])

    all_tools = set(TOOL_REGISTRY.keys())
    # Exclude internal tools from route requirement
    user_facing_tools = all_tools - ROUTE_EXEMPT
    unreachable = user_facing_tools - routed_tools
    assert not unreachable, (
        f"Tools in TOOL_REGISTRY with no route assignment ({len(unreachable)}): "
        + ", ".join(sorted(unreachable))
    )


# ── harness ────────────────────────────────────────────────────────────────

TESTS = [test_all_registry_tools_have_a_route]


def run_all() -> tuple[int, int]:
    passed = failed = 0
    for t in TESTS:
        try:
            t()
            print(f"  \u2713 routes: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 routes: {t.__name__}: {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    p, f = run_all()
    print(f"\n{p}/{p+f} passed")
