"""Tests for tools/goals.py — goals, plans, commitments CRUD.

Per ADR-038 Phase 2: tasks table deprecated. Tests for task functions removed.
"""

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
_TEST_COMMITMENT_IDS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    p, f = _run(TESTS)
    _teardown()
    return p, f


def _teardown():
    """Remove test commitments so they don't poison production."""
    try:
        from infra.db.schema import _exec
        # Delete test commitments
        if _TEST_COMMITMENT_IDS:
            placeholders = ",".join("?" * len(_TEST_COMMITMENT_IDS))
            _exec(
                f"DELETE FROM commitments WHERE id IN ({placeholders})",
                tuple(_TEST_COMMITMENT_IDS),
                commit=True,
            )
        # Also clean up by title as fallback
        _exec(
            "DELETE FROM commitments WHERE description LIKE 'Test%'",
            commit=True,
        )
    except Exception:
        pass


@test("goals: get_goals_list returns dict with count")
def test_get_goals():
    from tools.productivity.goals import get_goals_list
    result = get_goals_list()
    assert isinstance(result, dict), "Expected dict return"
    assert "count" in result, "Expected 'count' key"
    assert "goals" in result, "Expected 'goals' key"
    assert isinstance(result["goals"], list), "Expected list of goals"


@test("goals: get_current_plan returns dict or error")
def test_get_current_plan():
    from tools.productivity.goals import get_current_plan
    result = get_current_plan()
    assert isinstance(result, dict), "Expected dict return"


@test("goals: save_commitment creates db entry")
def test_save_commitment():
    from tools.productivity.goals import save_commitment
    result = save_commitment("Record Raccoin content", deadline="after June 15")
    assert isinstance(result, dict), "Expected dict return"
    assert result.get("status") == "saved", f"Expected status='saved', got {result.get('status')}"
    assert result.get("description") == "Record Raccoin content"
    assert result.get("deadline") == "after June 15"
    assert isinstance(result.get("commitment_id"), int), "Expected int commitment_id"
    if result.get("commitment_id"):
        _TEST_COMMITMENT_IDS.append(result["commitment_id"])


@test("goals: save_commitment without deadline works")
def test_save_commitment_no_deadline():
    from tools.productivity.goals import save_commitment
    result = save_commitment("Finish ReactReel landing page")
    assert isinstance(result, dict), "Expected dict return"
    assert result.get("status") == "saved"
    assert result.get("deadline") == "no deadline set"
    assert isinstance(result.get("commitment_id"), int)
    if result.get("commitment_id"):
        _TEST_COMMITMENT_IDS.append(result["commitment_id"])


@test("goals: list_commitments returns saved entry")
def test_list_commitments():
    from tools.productivity.goals import save_commitment
    from infra.db import list_commitments
    result = save_commitment("Test commitment for list check", deadline="2026-07-01")
    if result.get("commitment_id"):
        _TEST_COMMITMENT_IDS.append(result["commitment_id"])
    results = list_commitments()
    assert isinstance(results, list), "Expected list return"
    assert len(results) > 0, "Expected at least one commitment"
    descriptions = [r["description"] for r in results]
    assert "Test commitment for list check" in descriptions


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
