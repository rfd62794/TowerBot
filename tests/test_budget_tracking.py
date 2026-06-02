"""Tests for budget tracking database functions."""

import sys
import os
from datetime import datetime

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


@test("budget: budget_tracking table exists")
def test_table_exists():
    from infra.db.schema import _exec
    row = _exec(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='budget_tracking'"
    ).fetchone()
    assert row is not None, "budget_tracking table should exist"


@test("budget: get_or_create_budget creates new entry")
def test_get_or_create():
    from infra.db.budget_tracking import get_or_create_budget
    result = get_or_create_budget("test_provider", "test_model", 10.0)
    assert "daily_spent_usd" in result
    assert "daily_remaining_usd" in result
    assert result["daily_spent_usd"] == 0.0
    assert result["daily_remaining_usd"] == 10.0


@test("budget: record_cost updates spent and remaining")
def test_record_cost():
    from infra.db.budget_tracking import record_cost
    from infra.db.schema import _exec
    _exec("DELETE FROM budget_tracking WHERE provider='test_provider_2'", commit=True)
    result = record_cost("test_provider_2", "test_model_2", 1.5, 10.0)
    assert result["daily_spent_usd"] == 1.5, f"expected 1.5, got {result['daily_spent_usd']}"
    assert result["daily_remaining_usd"] == 8.5, f"expected 8.5, got {result['daily_remaining_usd']}"
    assert result["over_budget"] is False


@test("budget: record_cost detects over_budget")
def test_over_budget():
    from infra.db.budget_tracking import record_cost
    from infra.db.schema import _exec
    _exec("DELETE FROM budget_tracking WHERE provider='test_provider_3'", commit=True)
    result = record_cost("test_provider_3", "test_model_3", 12.0, 10.0)
    assert result["daily_spent_usd"] == 12.0, f"expected 12.0, got {result['daily_spent_usd']}"
    assert result["daily_remaining_usd"] == -2.0, f"expected -2.0, got {result['daily_remaining_usd']}"
    assert result["over_budget"] is True


@test("budget: get_budget_status returns percent_used")
def test_get_budget_status():
    from infra.db.budget_tracking import get_budget_status
    result = get_budget_status("test_provider_4", "test_model_4", 10.0)
    assert "percent_used" in result
    assert result["daily_cap_usd"] == 10.0
    assert result["over_budget"] in (True, False)


@test("budget: get_daily_spent returns total")
def test_get_daily_spent():
    from infra.db.budget_tracking import get_daily_spent
    from infra.db.schema import _exec
    _exec("DELETE FROM budget_tracking WHERE provider='test_provider_5'", commit=True)
    # Insert a row directly with today's date to avoid timezone issues
    _exec(
        """INSERT INTO budget_tracking 
           (provider, model_id, daily_cap_usd, daily_spent_usd, daily_remaining_usd, reset_at, recorded_at)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
        ("test_provider_5", "test_model_5", 10.0, 2.5, 7.5, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        commit=True
    )
    total = get_daily_spent("test_provider_5", "test_model_5")
    assert total >= 2.5, f"expected >= 2.5, got {total}"
    assert isinstance(total, float)


if __name__ == "__main__":
    passed, total = run_all()
    print(f"\n{passed}/{total} passed")
    sys.exit(0 if passed == total else 1)
