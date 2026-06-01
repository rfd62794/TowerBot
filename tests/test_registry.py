"""Tests for tools/registry.py — tool registration.

Pytest-style. run_all() shim retained for verify.py compatibility.
"""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def test_purge_null_tasks_in_registry():
    """Assert purge_null_tasks is present in TOOL_REGISTRY keys."""
    from tools.registry import TOOL_REGISTRY
    assert "purge_null_tasks" in TOOL_REGISTRY


# --- verify.py shim ---

def run_all() -> tuple[int, int]:
    passed, failed = 0, 0
    for fn in (test_purge_null_tasks_in_registry,):
        try:
            fn()
            print(f"✓ registry: {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"✗ registry: {fn.__name__}\n  {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    p, f = run_all()
    sys.exit(0 if f == 0 else 1)
