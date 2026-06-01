"""Tests for chain system schema — ADR-037 Phase 19.

All tests use isolated in-memory SQLite. No live privy.db. No network calls.
"""
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import pytest
from infra.db.schema import init_db


@pytest.fixture()
def test_db():
    from infra.db import schema
    schema.init_db(":memory:")
    yield schema._conn
    if schema._conn:
        schema._conn.close()
        schema._conn = None


def _table_columns(conn, table: str) -> set:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


# --- Schema existence tests ---

def test_chain_tables_exist(test_db):
    """All 5 new chain tables present after init_db()."""
    for table in ("chains", "chain_steps", "chain_payloads",
                  "pattern_candidates", "approval_listeners"):
        cols = _table_columns(test_db, table)
        assert cols, f"Table '{table}' missing or has no columns"


def test_pattern_candidates_table_exists(test_db):
    """pattern_candidates table exists with correct columns."""
    cols = _table_columns(test_db, "pattern_candidates")
    assert "id" in cols
    assert "step_sequence_hash" in cols
    assert "observed_count" in cols
    assert "success_rate" in cols
    assert "promotion_status" in cols


def test_approval_listeners_table_exists(test_db):
    """approval_listeners table exists with correct columns."""
    cols = _table_columns(test_db, "approval_listeners")
    assert "id" in cols
    assert "chain_id" in cols
    assert "step_id" in cols
    assert "telegram_chat_id" in cols
    assert "expires_at" in cols
    assert "status" in cols


# --- Chain CRUD tests ---

def test_create_chain(test_db):
    """create_chain() returns dict with id, template_name, status='running'."""
    from infra.db.chains import create_chain
    chain = create_chain("test_template")
    assert chain is not None
    assert "id" in chain
    assert chain["template_name"] == "test_template"
    assert chain["status"] == "running"
    assert chain["current_step"] == 0


def test_get_chain_returns_none_for_missing(test_db):
    """get_chain('nonexistent') returns None."""
    from infra.db.chains import get_chain
    assert get_chain("nonexistent-id") is None


def test_update_chain_status_complete(test_db):
    """update_chain_status sets completed_at when status='complete'."""
    from infra.db.chains import create_chain, update_chain_status, get_chain
    chain = create_chain("test_template")
    update_chain_status(chain["id"], "complete")
    updated = get_chain(chain["id"])
    assert updated["status"] == "complete"
    assert updated["completed_at"] is not None


def test_update_chain_status_running(test_db):
    """update_chain_status leaves completed_at None when status='running'."""
    from infra.db.chains import create_chain, update_chain_status, get_chain
    chain = create_chain("test_template")
    update_chain_status(chain["id"], "running", current_step=1)
    updated = get_chain(chain["id"])
    assert updated["status"] == "running"
    assert updated["completed_at"] is None
    assert updated["current_step"] == 1


def test_list_chains_filter_by_status(test_db):
    """list_chains(status='running') returns only running chains."""
    from infra.db.chains import create_chain, update_chain_status, list_chains
    c1 = create_chain("template_a")
    c2 = create_chain("template_b")
    update_chain_status(c2["id"], "complete")
    running = list_chains(status="running")
    running_ids = [c["id"] for c in running]
    assert c1["id"] in running_ids
    assert c2["id"] not in running_ids


# --- Step CRUD tests ---

def test_append_step(test_db):
    """append_step() returns dict with correct chain_id and step_index."""
    from infra.db.chains import create_chain, append_step
    chain = create_chain("test_template")
    step = append_step(chain["id"], 0, "tool_call", "fetch_data")
    assert step["chain_id"] == chain["id"]
    assert step["step_index"] == 0
    assert step["step_type"] == "tool_call"
    assert step["name"] == "fetch_data"
    assert step["status"] == "pending"


def test_get_steps_for_chain_ordered(test_db):
    """get_steps_for_chain returns steps in step_index order."""
    from infra.db.chains import create_chain, append_step, get_steps_for_chain
    chain = create_chain("test_template")
    append_step(chain["id"], 2, "transform", "step_c")
    append_step(chain["id"], 0, "tool_call", "step_a")
    append_step(chain["id"], 1, "llm_call", "step_b")
    steps = get_steps_for_chain(chain["id"])
    assert len(steps) == 3
    assert steps[0]["step_index"] == 0
    assert steps[1]["step_index"] == 1
    assert steps[2]["step_index"] == 2


def test_update_step_complete(test_db):
    """update_step sets completed_at when status='complete'."""
    from infra.db.chains import create_chain, append_step, update_step, get_step
    chain = create_chain("test_template")
    step = append_step(chain["id"], 0, "tool_call", "fetch_data")
    update_step(step["id"], "complete", error=None)
    updated = get_step(step["id"])
    assert updated["status"] == "complete"
    assert updated["completed_at"] is not None


# --- Payload CRUD tests ---

def test_create_payload(test_db):
    """create_payload() returns dict with deserialized data dict."""
    from infra.db.chains import create_chain
    from infra.db.payloads import create_payload
    chain = create_chain("test_template")
    payload = create_payload(chain["id"], "task_input", {"key": "value"})
    assert payload is not None
    assert "id" in payload
    assert payload["type"] == "task_input"
    assert isinstance(payload["data"], dict)
    assert payload["data"]["key"] == "value"
    assert payload["schema_version"] == "v1"


def test_payload_data_is_dict(test_db):
    """get_payload always returns data as dict, not string."""
    from infra.db.chains import create_chain
    from infra.db.payloads import create_payload, get_payload
    chain = create_chain("test_template")
    payload = create_payload(chain["id"], "result", {"score": 42})
    fetched = get_payload(payload["id"])
    assert isinstance(fetched["data"], dict)
    assert fetched["data"]["score"] == 42


def test_payload_type_error_on_string_data(test_db):
    """create_payload raises TypeError if data is a string."""
    from infra.db.chains import create_chain
    from infra.db.payloads import create_payload
    chain = create_chain("test_template")
    try:
        create_payload(chain["id"], "bad_payload", "this is a string")
        assert False, "Expected TypeError"
    except TypeError:
        pass


def test_list_payloads_for_chain(test_db):
    """list_payloads_for_chain returns payloads in created_at order."""
    from infra.db.chains import create_chain
    from infra.db.payloads import create_payload, list_payloads_for_chain
    chain = create_chain("test_template")
    create_payload(chain["id"], "input", {"step": 1})
    create_payload(chain["id"], "output", {"step": 2})
    payloads = list_payloads_for_chain(chain["id"])
    assert len(payloads) == 2
    assert all(isinstance(p["data"], dict) for p in payloads)


# --- run_all shim for verify.py ---

TESTS = [
    ("chain_tables_exist", test_chain_tables_exist),
    ("pattern_candidates_table_exists", test_pattern_candidates_table_exists),
    ("approval_listeners_table_exists", test_approval_listeners_table_exists),
    ("create_chain", test_create_chain),
    ("get_chain_returns_none_for_missing", test_get_chain_returns_none_for_missing),
    ("update_chain_status_complete", test_update_chain_status_complete),
    ("update_chain_status_running", test_update_chain_status_running),
    ("list_chains_filter_by_status", test_list_chains_filter_by_status),
    ("append_step", test_append_step),
    ("get_steps_for_chain_ordered", test_get_steps_for_chain_ordered),
    ("update_step_complete", test_update_step_complete),
    ("create_payload", test_create_payload),
    ("payload_data_is_dict", test_payload_data_is_dict),
    ("payload_type_error_on_string_data", test_payload_type_error_on_string_data),
    ("list_payloads_for_chain", test_list_payloads_for_chain),
]


def run_all() -> tuple[int, int]:
    import infra.db.schema as _schema
    passed = failed = 0
    for name, fn in TESTS:
        _schema.init_db(":memory:")
        conn = _schema._conn
        try:
            fn(conn)
            print(f"  \u2713 chain_schema: {name}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 chain_schema: {name}: {e}")
            failed += 1
        finally:
            if _schema._conn:
                _schema._conn.close()
                _schema._conn = None
    return passed, failed


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
