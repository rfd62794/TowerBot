"""Tests for Phase 20c — observer, digest, template loader, production wiring.

All tests use isolated in-memory SQLite. No real Telegram calls.
"""
import os
import sys
import tempfile
from pathlib import Path

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


# --- template_loader.py tests ---

def test_load_template_canonical(test_db):
    """load_template('hourly_fact') returns dict with name and steps."""
    from infra.chain.template_loader import load_template
    t = load_template("hourly_fact")
    assert t["name"] == "hourly_fact"
    assert "steps" in t
    assert len(t["steps"]) > 0


def test_load_template_not_found(test_db):
    """load_template('nonexistent') raises TemplateError."""
    from infra.chain.template_loader import load_template, TemplateError
    try:
        load_template("nonexistent")
        assert False, "Expected TemplateError"
    except TemplateError:
        pass


def test_load_template_missing_steps(test_db):
    """YAML without steps raises TemplateError."""
    from infra.chain.template_loader import _load_and_validate, TemplateError
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "bad.yaml"
        path.write_text("name: test\n")
        try:
            _load_and_validate(path)
            assert False, "Expected TemplateError"
        except TemplateError:
            pass


def test_load_template_invalid_step_type(test_db):
    """Step with unknown type raises TemplateError."""
    from infra.chain.template_loader import _load_and_validate, TemplateError
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "bad.yaml"
        path.write_text("name: test\nsteps:\n  - type: unknown_xyz\n")
        try:
            _load_and_validate(path)
            assert False, "Expected TemplateError"
        except TemplateError:
            pass


def test_list_templates_canonical(test_db):
    """list_templates('canonical') includes hourly_fact."""
    from infra.chain.template_loader import list_templates
    templates = list_templates("canonical")
    names = [t["name"] for t in templates]
    assert "hourly_fact" in names


def test_list_templates_skips_invalid(test_db):
    """Invalid YAML in canonical dir — still returns other templates."""
    from infra.chain.template_loader import list_templates, CANONICAL_DIR
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch canonical dir to temp dir with one bad and one good file
        bad = Path(tmpdir) / "bad.yaml"
        bad.write_text("invalid: yaml: [")
        good = Path(tmpdir) / "good.yaml"
        good.write_text("name: good\nsteps:\n  - type: transform\n")
        original = CANONICAL_DIR
        import infra.chain.template_loader as tl
        tl.CANONICAL_DIR = Path(tmpdir)
        try:
            templates = list_templates("canonical")
            assert len(templates) == 1
            assert templates[0]["name"] == "good"
        finally:
            tl.CANONICAL_DIR = original


# --- observer.py tests ---

def test_observer_new_candidate(test_db):
    """observe_completed_chains() with one chain — creates candidate row."""
    from infra.db.chains import create_chain, append_step, update_step, update_chain_status
    from infra.chain.observer import observe_completed_chains
    chain = create_chain("test_template")
    step = append_step(chain["id"], 0, "transform", "step1")
    update_step(step["id"], status="complete")
    update_chain_status(chain["id"], "complete")
    result = observe_completed_chains()
    assert result["candidates_new"] == 1


def test_observer_increments_count(test_db):
    """Second observation of same sequence — count becomes 2."""
    from infra.db.chains import create_chain, append_step, update_step, update_chain_status
    from infra.chain.observer import observe_completed_chains
    chain = create_chain("test_template")
    step = append_step(chain["id"], 0, "transform", "step1")
    update_step(step["id"], status="complete")
    update_chain_status(chain["id"], "complete")
    observe_completed_chains()
    result = observe_completed_chains()
    assert result["candidates_updated"] == 1


def test_observer_promotes_after_threshold(test_db):
    """3 observations at high success rate — status becomes ready_to_promote."""
    from infra.db.chains import create_chain, append_step, update_step, update_chain_status
    from infra.chain.observer import observe_completed_chains
    from infra.db.schema import _exec
    chain = create_chain("test_template")
    step = append_step(chain["id"], 0, "transform", "step1")
    update_step(step["id"], status="complete")
    update_chain_status(chain["id"], "complete")
    # Run 3 times to hit threshold
    observe_completed_chains()
    observe_completed_chains()
    observe_completed_chains()
    row = _exec("SELECT * FROM pattern_candidates").fetchone()
    assert row["promotion_status"] == "ready_to_promote"


def test_observer_empty_no_error(test_db):
    """No completed chains — returns zeros, no crash."""
    from infra.chain.observer import observe_completed_chains
    result = observe_completed_chains()
    assert result["chains_scanned"] == 0
    assert result["candidates_new"] == 0


def test_sequence_hash_consistent(test_db):
    """Same steps → same hash on two calls."""
    from infra.chain.observer import _sequence_hash
    steps = [{"step_type": "transform", "name": "s1"}]
    h1 = _sequence_hash(steps)
    h2 = _sequence_hash(steps)
    assert h1 == h2


def test_sequence_hash_differs(test_db):
    """Different step names → different hash."""
    from infra.chain.observer import _sequence_hash
    h1 = _sequence_hash([{"step_type": "transform", "name": "s1"}])
    h2 = _sequence_hash([{"step_type": "transform", "name": "s2"}])
    assert h1 != h2


def test_get_promotion_candidates_empty(test_db):
    """No ready candidates — returns empty list."""
    from infra.chain.observer import get_promotion_candidates
    assert get_promotion_candidates() == []


def test_get_promotion_candidates_returns_ready(test_db):
    """Insert ready_to_promote row — returned by get_promotion_candidates."""
    from infra.chain.observer import get_promotion_candidates
    from infra.db.schema import _exec
    import uuid
    _exec(
        """INSERT INTO pattern_candidates
           (id, step_sequence_hash, observed_count, first_seen, last_seen,
            success_rate, promotion_status)
           VALUES (?, ?, 5, '2024-01-01', '2024-01-01', 0.9, 'ready_to_promote')""",
        (str(uuid.uuid4()), "hash123"),
        commit=True
    )
    candidates = get_promotion_candidates()
    assert len(candidates) == 1
    assert candidates[0]["promotion_status"] == "ready_to_promote"


# --- integration tests ---

def test_hourly_fact_template_valid(test_db):
    """hourly_fact.yaml loads and validates without error."""
    from infra.chain.template_loader import load_template
    t = load_template("hourly_fact")
    assert t is not None


def test_hourly_fact_has_three_steps(test_db):
    """hourly_fact template has exactly 3 steps."""
    from infra.chain.template_loader import load_template
    t = load_template("hourly_fact")
    assert len(t["steps"]) == 3


def test_resume_fn_loads_template(test_db):
    """Mock load_template — _build_resume_fn calls it with chain's template_name."""
    from bot.approval_router import _build_resume_fn
    from infra.db.chains import create_chain
    chain = create_chain("hourly_fact")
    calls = []
    def mock_load(name):
        calls.append(name)
        return {"name": name, "steps": []}
    from infra.chain import template_loader
    original = template_loader.load_template
    template_loader.load_template = mock_load
    try:
        resume_fn = _build_resume_fn()
        resume_fn(chain["id"])
        assert "hourly_fact" in calls
    finally:
        template_loader.load_template = original


def test_resume_fn_handles_template_error(test_db):
    """load_template raises — resume_fn returns without crash."""
    from bot.approval_router import _build_resume_fn
    from infra.db.chains import create_chain
    from infra.chain.template_loader import TemplateError
    chain = create_chain("bad_template")
    def mock_load(name):
        raise TemplateError("bad")
    from infra.chain import template_loader
    original = template_loader.load_template
    template_loader.load_template = mock_load
    try:
        resume_fn = _build_resume_fn()
        resume_fn(chain["id"])  # Should not crash
    finally:
        template_loader.load_template = original


def test_runner_integration_two_steps(test_db):
    """ChainRunner.run() with two transform steps — chain status 'complete'."""
    from infra.db.chains import create_chain
    from infra.chain.runner import ChainRunner
    chain = create_chain("test_template")
    runner = ChainRunner()
    steps = [
        {"name": "s1", "type": "transform", "config": {"map": {"x": "y"}}},
        {"name": "s2", "type": "transform", "config": {"map": {"a": "b"}}}
    ]
    result = runner.run(chain["id"], steps)
    assert result["status"] == "complete"


def test_observer_success_rate_calculation(test_db):
    """Mixed complete/failed steps — success_rate calculated correctly."""
    from infra.db.chains import create_chain, append_step, update_step, update_chain_status
    from infra.chain.observer import observe_completed_chains
    from infra.db.schema import _exec
    chain = create_chain("test_template")
    s1 = append_step(chain["id"], 0, "transform", "s1")
    s2 = append_step(chain["id"], 1, "transform", "s2")
    update_step(s1["id"], status="complete")
    update_step(s2["id"], status="failed")
    update_chain_status(chain["id"], "complete")
    observe_completed_chains()
    row = _exec("SELECT * FROM pattern_candidates").fetchone()
    assert row["success_rate"] == 0.5


# --- run_all shim for verify.py ---

TESTS = [
    ("load_template_canonical", test_load_template_canonical),
    ("load_template_not_found", test_load_template_not_found),
    ("load_template_missing_steps", test_load_template_missing_steps),
    ("load_template_invalid_step_type", test_load_template_invalid_step_type),
    ("list_templates_canonical", test_list_templates_canonical),
    ("list_templates_skips_invalid", test_list_templates_skips_invalid),
    ("observer_new_candidate", test_observer_new_candidate),
    ("observer_increments_count", test_observer_increments_count),
    ("observer_promotes_after_threshold", test_observer_promotes_after_threshold),
    ("observer_empty_no_error", test_observer_empty_no_error),
    ("sequence_hash_consistent", test_sequence_hash_consistent),
    ("sequence_hash_differs", test_sequence_hash_differs),
    ("get_promotion_candidates_empty", test_get_promotion_candidates_empty),
    ("get_promotion_candidates_returns_ready", test_get_promotion_candidates_returns_ready),
    ("hourly_fact_template_valid", test_hourly_fact_template_valid),
    ("hourly_fact_has_three_steps", test_hourly_fact_has_three_steps),
    ("resume_fn_loads_template", test_resume_fn_loads_template),
    ("resume_fn_handles_template_error", test_resume_fn_handles_template_error),
    ("runner_integration_two_steps", test_runner_integration_two_steps),
    ("observer_success_rate_calculation", test_observer_success_rate_calculation),
]


def run_all() -> tuple[int, int]:
    import infra.db.schema as _schema
    passed = failed = 0
    for name, fn in TESTS:
        _schema.init_db(":memory:")
        conn = _schema._conn
        try:
            fn(conn)
            print(f"  \u2713 phase20c: {name}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 phase20c: {name}: {e}")
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
