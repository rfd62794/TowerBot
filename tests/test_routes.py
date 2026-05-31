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
    unreachable = all_tools - routed_tools
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
