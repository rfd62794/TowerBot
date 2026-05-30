"""Tests for deploy_history table and functions."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

_tests = []
_results = []


def test(fn):
    _tests.append(fn)
    return fn


@test
def test_deploy_history_table_exists():
    from core.db.schema import _exec
    cur = _exec(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='deploy_history'"
    )
    row = cur.fetchone()
    assert row is not None, "deploy_history table missing"


@test
def test_record_deploy_creates_entry():
    from core.db import record_deploy, get_last_deploy
    deploy_id = record_deploy("abc1234", "test: record deploy")
    assert isinstance(deploy_id, int) and deploy_id > 0
    last = get_last_deploy()
    assert last is not None
    assert last["commit_hash"] == "abc1234"
    assert last["commit_message"] == "test: record deploy"
    assert last["verify_passed"] == 0
    assert last["stable"] == 0


@test
def test_mark_stable_updates_entry():
    from core.db import record_deploy, mark_verify_passed, mark_stable, get_last_deploy
    deploy_id = record_deploy("def5678", "test: mark stable")
    mark_verify_passed(deploy_id)
    mark_stable(deploy_id)
    last = get_last_deploy()
    assert last["verify_passed"] == 1
    assert last["stable"] == 1


@test
def test_get_last_stable_commit_returns_dict():
    from core.db import record_deploy, mark_verify_passed, mark_stable, get_last_stable_commit
    deploy_id = record_deploy("ghi9012", "test: stable commit")
    mark_verify_passed(deploy_id)
    mark_stable(deploy_id)
    stable = get_last_stable_commit()
    assert stable is not None
    assert isinstance(stable, dict)
    assert stable["stable"] == 1
    assert stable["commit_hash"] == "ghi9012"


@test
def test_get_last_deploy_returns_dict():
    from core.db import record_deploy, get_last_deploy
    record_deploy("jkl3456", "test: last deploy")
    last = get_last_deploy()
    assert last is not None
    assert isinstance(last, dict)
    assert "commit_hash" in last
    assert "deployed_at" in last


_TEST_HASHES = ["abc1234", "def5678", "ghi9012", "jkl3456"]


def _teardown():
    """Remove test deploy records so they don't poison the health check."""
    try:
        from core.db.schema import _exec
        placeholders = ",".join("?" * len(_TEST_HASHES))
        _exec(
            f"DELETE FROM deploy_history WHERE commit_hash IN ({placeholders})",
            tuple(_TEST_HASHES),
            commit=True,
        )
    except Exception:
        pass


def run_all() -> tuple[int, int]:
    passed = 0
    failed = 0
    for fn in _tests:
        try:
            fn()
            print(f"✓ deployments: {fn.__name__.replace('test_', '').replace('_', ' ')}")
            passed += 1
        except Exception as e:
            print(f"✗ deployments: {fn.__name__.replace('test_', '').replace('_', ' ')} — {e}")
            failed += 1
    _teardown()
    return passed, failed


if __name__ == "__main__":
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
