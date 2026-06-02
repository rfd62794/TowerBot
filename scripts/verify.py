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

from infra.db import init_db
init_db()

TEST_FILES = [
    "tests/test_db.py",
    "tests/test_memory.py",
    "tests/test_core.py",
    "tests/test_model_usage.py",
    "tests/test_resources.py",
    "tests/test_budget_tracking.py",
    "tests/test_openrouter_api.py",
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
    "tests/test_cache_manager.py",
    "tests/test_base_classes.py",
    "tests/test_fetch_think.py",
    "tests/test_rate_limits.py",
    "tests/test_polling.py",
    "tests/test_briefing.py",
    "tests/test_tools_repo.py",
    "tests/test_ollama_vram.py",
    "tests/test_ollama_routing.py",
    "tests/test_transport.py",
    "tests/test_routes.py",
    "tests/test_router_ai.py",
    "tests/test_agent_routing.py",
    "tests/test_memory_semantic.py",
    "tests/test_mcp.py",
    "tests/test_deploy.py",
    "tests/test_task_runner.py",
    "tests/test_autonomous.py",
    "tests/test_delegation.py",
    "tests/test_prompts.py",
    "tests/test_auto_update.py",
    "tests/test_update.py",
    "tests/test_router.py",
    "tests/test_registry.py",
    "tests/test_chain_schema.py",
    "tests/test_chain_runner.py",
    "tests/test_approval.py",
    "tests/test_phase20c.py",
    "tests/test_admin_tools.py",
    "tests/test_phase21.py",
    "tests/test_director_tools.py",
    "tests/test_tool_registry.py",
    "tests/test_model_wiring.py",
    "tests/test_wordpress_pages.py",
]


def _load_and_run(path: str) -> tuple[int, int]:
    """Load a test module and run its tests. Returns (passed, failed)."""
    full_path = os.path.join(_root, path)
    if not os.path.exists(full_path):
        return -1, 0
    spec = importlib.util.spec_from_file_location("_test_module", full_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run_all()


def run_all():
    total_passed = 0
    total_failed = 0
    total_skipped = 0
    file_results = []

    for test_file in TEST_FILES:
        p, f = _load_and_run(test_file)
        if p == -1:
            total_skipped += 1
            file_results.append((test_file, "MISSING", 0, 0))
            continue
        total_passed += p
        total_failed += f
        file_results.append((test_file, "ok" if f == 0 else "FAIL", p, f))

    print()
    print("=" * 60)
    print(f"  {'FILE':<38} {'PASS':>5} {'FAIL':>5}")
    print("-" * 60)
    for path, status, p, f in file_results:
        label = os.path.basename(path)
        if status == "MISSING":
            print(f"  [missing]  {label}")
        elif status == "FAIL":
            print(f"  [FAIL]     {label:<34} {p:>5} {f:>5}")
        else:
            print(f"  [ok]       {label:<34} {p:>5}")
    print("=" * 60)

    total = total_passed + total_failed
    skip_note = f"  ({total_skipped} missing)" if total_skipped else ""
    print(f"  TOTAL  {total_passed} passed  {total_failed} failed{skip_note}")
    print()

    if total_failed == 0:
        print("Deploy safe.")
        sys.exit(0)
    else:
        print("Deploy blocked.")
        sys.exit(1)


if __name__ == "__main__":
    run_all()
