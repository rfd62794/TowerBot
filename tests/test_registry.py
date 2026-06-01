"""Tests for tools/registry.py — tool registration."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def test_decorator(name):
    def wrapper(fn):
        fn.__name__ = name
        TESTS.append((name, fn))
        return fn
    return wrapper

test = test_decorator

TESTS = []


@test("registry: purge_null_tasks in TOOL_REGISTRY")
def test_purge_null_tasks_in_registry():
    """Assert purge_null_tasks is present in TOOL_REGISTRY keys."""
    from tools.registry import TOOL_REGISTRY
    assert "purge_null_tasks" in TOOL_REGISTRY


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


if __name__ == "__main__":
    passed, failed = run_all()
    print(f"\n{passed}/{passed + failed} passed.", end=" ")
    if failed == 0:
        print("Deploy safe.")
        sys.exit(0)
    else:
        print("Deploy blocked.")
        sys.exit(1)
