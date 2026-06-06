"""Tests for task runner — YAML loading and task resolution."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db
init_db()

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


@test("task_runner: resolve_task email_triage has persona")
def test_resolve_task_email_triage_has_persona():
    from bot.task_runner import resolve_task
    task = resolve_task("email_triage")
    assert task["persona"], "Task should have persona"
    assert "Summarize clearly" in task["persona"] or "Monitor" in task["persona"]


@test("task_runner: resolve_task planner has 25 iterations")
def test_resolve_task_planner_has_25_iterations():
    from bot.task_runner import resolve_task
    task = resolve_task("self_expansion_planner")
    assert task["max_iterations"] == 25, f"Expected 25, got {task['max_iterations']}"


@test("task_runner: resolve_task monitor has 5 iterations")
def test_resolve_task_monitor_has_5_iterations():
    from bot.task_runner import resolve_task
    task = resolve_task("itch_reddit_check")
    assert task["max_iterations"] == 5, f"Expected 5, got {task['max_iterations']}"


@test("task_runner: resolve_task missing template raises")
def test_resolve_task_missing_template_raises():
    from bot.task_runner import resolve_task
    try:
        resolve_task("nonexistent_task")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "not found" in str(e).lower()


@test("task_runner: resolve_task prompt fills params")
def test_resolve_task_prompt_fills_params():
    from bot.task_runner import resolve_task
    task = resolve_task("itch_reddit_check")
    assert "{subreddits}" not in task["prompt"], "Params should be filled"
    assert "r/incremental_games" in task["prompt"], "Should contain filled param"


@test("task_runner: get_all_resolved_tasks returns six")
def test_get_all_resolved_tasks_returns_six():
    from bot.task_runner import get_all_resolved_tasks
    tasks = get_all_resolved_tasks()
    assert len(tasks) == 6, f"Expected 6 tasks, got {len(tasks)}"


@test("task_runner: get_all_resolved_tasks skips disabled")
def test_get_all_resolved_tasks_skips_disabled():
    from bot.task_runner import load_tasks, get_all_resolved_tasks
    tasks = load_tasks()
    # Count enabled tasks that can be resolved (template exists)
    # Some tasks may be enabled but have missing templates
    enabled_count = 0
    for name, task in tasks.items():
        if task.get("enabled", True):
            # Check if template can be loaded
            try:
                from bot.task_runner import resolve_task
                resolve_task(name)
                enabled_count += 1
            except ValueError:
                # Template not found, skip
                pass
    resolved = get_all_resolved_tasks()
    assert len(resolved) == enabled_count, f"Expected {enabled_count}, got {len(resolved)}"


@test("task_runner: task urgent_on keywords from type")
def test_task_urgent_on_keywords_from_type():
    from bot.task_runner import resolve_task
    task = resolve_task("nightly_snapshot")
    assert task["urgent_on"], "Reporter task should have urgent_on keywords"
    assert "spike" in task["urgent_on"] or "urgent" in task["urgent_on"]


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
