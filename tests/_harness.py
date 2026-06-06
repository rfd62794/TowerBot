"""Test harness — @test decorator and run_all() shared by every test file."""

import sys
import inspect

TESTS = []


def test(name):
    """Decorator that registers a test function."""
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all(tests=None) -> tuple[int, int]:
    """Run all registered tests. Returns (passed, failed)."""
    registry = tests if tests is not None else TESTS
    passed = 0
    failed = 0
    for name, func in registry:
        try:
            func()
            print(f"✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}")
            print(f"  AssertionError: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}")
            print(f"  {type(e).__name__}: {e}")
            failed += 1
    return passed, failed


def auto_run(module=None) -> tuple[int, int]:
    """Auto-discover test_* functions from calling module and run them."""
    if module is None:
        frame = inspect.stack()[1]
        module = sys.modules[frame[0].f_globals['__name__']]
    tests = [
        (obj.__name__, obj) for name, obj in inspect.getmembers(module, inspect.isfunction)
        if name.startswith('test_') and not name.startswith('test_decorator')
    ]
    return run_all(tests)
