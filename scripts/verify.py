"""PrivyBot verification script — gate between laptop and Tower.

Runner only. Discovers and executes all test files in tests/.
Exit code 0 = pass (deploy safe)
Exit code 1 = fail (deploy blocked)
"""

import sys
import os
import importlib.util

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from core.db import init_db
init_db()

TEST_FILES = [
    "tests/test_db.py",
    "tests/test_memory.py",
    "tests/test_core.py",
    "tests/test_tools_youtube.py",
    "tests/test_tools_games.py",
    "tests/test_tools_search.py",
    "tests/test_tools_goals.py",
    "tests/test_api.py",
    "tests/test_deployments.py",
    "tests/test_personal_tasks.py",
    "tests/test_google_tasks_sync.py",
    "tests/test_google_calendar.py",
    "tests/test_gmail.py",
    "tests/test_offline_cache.py",
]


def _load_and_run(path: str) -> tuple[int, int]:
    """Load a test module and run its tests. Returns (passed, failed)."""
    full_path = os.path.join(_root, path)
    if not os.path.exists(full_path):
        print(f"  ⚠ {path}: file not found, skipping")
        return 0, 0
    spec = importlib.util.spec_from_file_location("_test_module", full_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run_all()


def run_all():
    total_passed = 0
    total_failed = 0

    for test_file in TEST_FILES:
        p, f = _load_and_run(test_file)
        total_passed += p
        total_failed += f

    print()
    total = total_passed + total_failed
    print(f"{total_passed}/{total} passed.", end=" ")

    if total_failed == 0:
        print("Deploy safe.")
        sys.exit(0)
    else:
        print("Deploy blocked.")
        sys.exit(1)

if __name__ == "__main__":
    run_all()
