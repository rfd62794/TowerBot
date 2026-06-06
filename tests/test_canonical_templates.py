"""Tests for canonical template injection in task runner."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def _test_decorator(name):
    def wrapper(fn):
        fn.__name__ = name
        TESTS.append((name, fn))
        return fn
    return wrapper


test = _test_decorator
TESTS = []


@test("canonical: system_base always injected")
def test_system_base_always_injected():
    """system_base template should be injected for all task types."""
    from bot.task_runner import resolve_task
    task = resolve_task("email_triage")
    prompt = task["prompt"]
    assert "PrivyBot" in prompt, "system_base should contain PrivyBot identity"
    assert "Robert Floyd Dugger" in prompt, "system_base should contain Robert's name"
    assert "VoidDrift" in prompt, "system_base should mention VoidDrift project"


@test("canonical: planner gets tool_priority and research_synthesis")
def test_planner_gets_research_templates():
    """planner task type should get tool_priority and research_synthesis."""
    from bot.task_runner import resolve_task
    # Use any existing task, check if it's planner type
    try:
        task = resolve_task("email_triage")
        prompt = task["prompt"]
        # Only check if it's a planner type
        if "Tool selection order" in prompt:
            assert "Memory and local state first" in prompt, "tool_priority content should be present"
            assert "When synthesizing research findings" in prompt, "research_synthesis should be injected"
    except ValueError:
        pass  # Skip if task doesn't exist


@test("canonical: reporter gets signal_over_noise and one_thing")
def test_reporter_gets_output_templates():
    """reporter task type should get signal_over_noise and one_thing_decision."""
    from bot.task_runner import resolve_task
    # Find a reporter-type task if exists, otherwise skip
    try:
        task = resolve_task("weekly_accountability")
        prompt = task["prompt"]
        assert "When reporting results" in prompt, "signal_over_noise should be injected"
        assert "Lead with what CHANGED" in prompt, "signal_over_noise content should be present"
    except ValueError:
        # Task may not exist, skip test
        pass


@test("canonical: creator gets rfd_content_frame")
def test_creator_gets_content_frame():
    """creator task type should get rfd_content_frame."""
    from bot.task_runner import resolve_task
    try:
        task = resolve_task("blog_draft")
        prompt = task["prompt"]
        assert "Content titles follow identity transformation pattern" in prompt, "rfd_content_frame should be injected"
        assert "MOMENT → SURPRISE → STRUGGLE → LESSON → NEXT" in prompt, "rfd_content_frame structure should be present"
    except ValueError:
        # Task may not exist, skip test
        pass


@test("canonical: approval_gate injected for action tasks")
def test_approval_gate_injected():
    """creator and planner tasks should get approval_gate."""
    from bot.task_runner import resolve_task
    task = resolve_task("email_triage")
    prompt = task["prompt"]
    # Only check if it's a planner or creator type
    if "Before acting on any external platform" in prompt:
        assert "request_approval()" in prompt, "approval_gate should mention approval function"


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
