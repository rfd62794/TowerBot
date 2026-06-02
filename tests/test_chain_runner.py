"""Tests for chain runner and step handlers — Phase 20a.

All tests use isolated in-memory SQLite. No real LLM calls. No network.
Dependencies injected via ChainRunner constructor.
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


# --- Runner integration tests ---

def test_runner_completes_simple_chain(test_db):
    """Single transform step — chain status becomes 'complete'."""
    from infra.db.chains import create_chain
    from infra.chain.runner import ChainRunner
    chain = create_chain("test_template")
    runner = ChainRunner()
    step_defs = [{'name': 'add_flag', 'type': 'transform',
                  'config': {'mapping': {'done': True}}}]
    result = runner.run(chain['id'], step_defs)
    assert result['status'] == 'complete'


def test_runner_resumes_from_current_step(test_db):
    """Chain with current_step=1 skips step 0, runs step 1 only."""
    from infra.db.chains import create_chain, update_chain_status
    from infra.db.payloads import create_payload
    from infra.chain.runner import ChainRunner
    chain = create_chain("test_template")
    update_chain_status(chain['id'], 'running', current_step=1)
    calls = []
    def mock_tool(**kwargs):
        calls.append(kwargs)
        return 'called'
    runner = ChainRunner(tool_registry={'mock_tool': mock_tool})
    step_defs = [
        {'name': 'step_skipped', 'type': 'transform',
         'config': {'mapping': {'s0': True}}},
        {'name': 'step_run', 'type': 'tool_call',
         'config': {'tool_name': 'mock_tool', 'tool_args': {}}},
    ]
    result = runner.run(chain['id'], step_defs)
    assert result['status'] == 'complete'
    assert len(calls) == 1


def test_runner_skips_complete_chain(test_db):
    """Chain with status='complete' — run() returns immediately."""
    from infra.db.chains import create_chain, update_chain_status
    from infra.chain.runner import ChainRunner
    chain = create_chain("test_template")
    update_chain_status(chain['id'], 'complete')
    calls = []
    def mock_tool(**kwargs):
        calls.append(kwargs)
        return 'should not be called'
    runner = ChainRunner(tool_registry={'mock_tool': mock_tool})
    step_defs = [{'name': 's0', 'type': 'tool_call',
                  'config': {'tool_name': 'mock_tool', 'tool_args': {}}}]
    result = runner.run(chain['id'], step_defs)
    assert result['status'] == 'complete'
    assert len(calls) == 0


def test_runner_skips_failed_chain(test_db):
    """Chain with status='failed' — run() returns immediately."""
    from infra.db.chains import create_chain, update_chain_status
    from infra.chain.runner import ChainRunner
    chain = create_chain("test_template")
    update_chain_status(chain['id'], 'failed')
    calls = []
    runner = ChainRunner(tool_registry={'t': lambda: calls.append(1)})
    step_defs = [{'name': 's0', 'type': 'transform',
                  'config': {'mapping': {'x': 1}}}]
    result = runner.run(chain['id'], step_defs)
    assert result['status'] == 'failed'
    assert len(calls) == 0


def test_runner_persists_after_each_step(test_db):
    """After each step, chain_steps row exists in DB with correct status."""
    from infra.db.chains import create_chain, get_steps_for_chain
    from infra.chain.runner import ChainRunner
    chain = create_chain("test_template")
    runner = ChainRunner()
    step_defs = [
        {'name': 'step_a', 'type': 'transform',
         'config': {'mapping': {'a': 1}}},
        {'name': 'step_b', 'type': 'transform',
         'config': {'mapping': {'b': 2}}},
    ]
    runner.run(chain['id'], step_defs)
    steps = get_steps_for_chain(chain['id'])
    assert len(steps) == 2
    assert all(s['status'] == 'complete' for s in steps)


def test_runner_marks_chain_failed_on_step_error(test_db):
    """Step raises StepError — chain status becomes 'failed'."""
    from infra.db.chains import create_chain
    from infra.chain.runner import ChainRunner
    chain = create_chain("test_template")
    def bad_tool(**kwargs):
        raise RuntimeError("tool exploded")
    runner = ChainRunner(tool_registry={'bad_tool': bad_tool})
    step_defs = [{'name': 'boom', 'type': 'tool_call',
                  'config': {'tool_name': 'bad_tool', 'tool_args': {}}}]
    result = runner.run(chain['id'], step_defs)
    assert result['status'] == 'failed'


def test_runner_pauses_on_step_skipped(test_db):
    """Step raises StepSkipped — chain status becomes 'waiting_approval'."""
    from infra.db.chains import create_chain
    from infra.chain.runner import ChainRunner
    chain = create_chain("test_template")
    runner = ChainRunner()
    step_defs = [{'name': 'wait', 'type': 'approval_wait', 'config': {}}]
    result = runner.run(chain['id'], step_defs)
    assert result['status'] == 'waiting_approval'


def test_runner_unknown_step_type_fails_chain(test_db):
    """Step type 'unknown_xyz' — chain status becomes 'failed'."""
    from infra.db.chains import create_chain
    from infra.chain.runner import ChainRunner
    chain = create_chain("test_template")
    runner = ChainRunner()
    step_defs = [{'name': 'mystery', 'type': 'unknown_xyz', 'config': {}}]
    result = runner.run(chain['id'], step_defs)
    assert result['status'] == 'failed'


def test_payload_persisted_for_each_step(test_db):
    """After 2-step chain, chain_payloads has 4 rows (input+output per step)."""
    from infra.db.chains import create_chain
    from infra.db.payloads import list_payloads_for_chain
    from infra.chain.runner import ChainRunner
    chain = create_chain("test_template")
    runner = ChainRunner()
    step_defs = [
        {'name': 'step_a', 'type': 'transform',
         'config': {'mapping': {'a': 1}}},
        {'name': 'step_b', 'type': 'transform',
         'config': {'mapping': {'b': 2}}},
    ]
    runner.run(chain['id'], step_defs)
    payloads = list_payloads_for_chain(chain['id'])
    assert len(payloads) == 4


# --- Step handler unit tests ---

def test_tool_call_handler_executes_tool(test_db):
    """Mock tool in registry — handle_tool_call returns payload with tool_result."""
    from infra.chain.steps import handle_tool_call
    mock_tool = lambda **kw: {'status': 'ok'}
    step = {'id': 'step-1', 'config': {'tool_name': 'mock_tool', 'tool_args': {}}}
    result = handle_tool_call(step, {'x': 1}, {'mock_tool': mock_tool})
    assert 'tool_result' in result
    assert result['tool_result']['status'] == 'ok'
    assert result['x'] == 1


def test_tool_call_handler_missing_tool(test_db):
    """Tool not in registry — raises StepError."""
    from infra.chain.steps import handle_tool_call, StepError
    step = {'id': 'step-1', 'config': {'tool_name': 'missing', 'tool_args': {}}}
    try:
        handle_tool_call(step, {}, {})
        assert False, "Expected StepError"
    except StepError:
        pass


def test_tool_call_handler_resolves_args(test_db):
    """Arg '{title}' resolves to payload['title']."""
    from infra.chain.steps import handle_tool_call
    received = {}
    def capture_tool(**kwargs):
        received.update(kwargs)
        return 'ok'
    step = {'id': 'step-1', 'config': {
        'tool_name': 'capture_tool',
        'tool_args': {'name': '{title}'}
    }}
    handle_tool_call(step, {'title': 'My Title'}, {'capture_tool': capture_tool})
    assert received['name'] == 'My Title'


def test_llm_call_handler_calls_model(test_db):
    """Mock call_model_fn — handle_llm_call returns payload with llm_result."""
    from infra.chain.steps import handle_llm_call
    mock_model = lambda prompt, role: f"response to {role}"
    step = {'id': 'step-1', 'config': {'prompt_template': 'hello', 'model_role': 'reasoning'}}
    result = handle_llm_call(step, {'x': 1}, mock_model)
    assert 'llm_result' in result
    assert result['llm_result'] == 'response to reasoning'


def test_llm_call_handler_resolves_template(test_db):
    """Prompt '{title}' resolves to payload['title']."""
    from infra.chain.steps import handle_llm_call
    prompts = []
    def capture_model(prompt, role):
        prompts.append(prompt)
        return 'ok'
    step = {'id': 'step-1', 'config': {'prompt_template': 'Write about {title}'}}
    handle_llm_call(step, {'title': 'Python'}, capture_model)
    assert prompts[0] == 'Write about Python'


def test_condition_check_eq_true(test_db):
    """field='x', op='eq', value=1, payload={'x':1} — condition_met=True."""
    from infra.chain.steps import handle_condition_check
    step = {'id': 'step-1', 'config': {'field': 'x', 'operator': 'eq', 'value': 1}}
    result = handle_condition_check(step, {'x': 1})
    assert result['condition_met'] is True


def test_condition_check_eq_false(test_db):
    """field='x', op='eq', value=1, payload={'x':2} — condition_met=False."""
    from infra.chain.steps import handle_condition_check
    step = {'id': 'step-1', 'config': {'field': 'x', 'operator': 'eq', 'value': 1}}
    result = handle_condition_check(step, {'x': 2})
    assert result['condition_met'] is False


def test_condition_check_skip_if_false(test_db):
    """skip_if_false=True, condition False — raises StepSkipped."""
    from infra.chain.steps import handle_condition_check, StepSkipped
    step = {'id': 'step-1', 'config': {
        'field': 'x', 'operator': 'eq', 'value': 1, 'skip_if_false': True
    }}
    try:
        handle_condition_check(step, {'x': 99})
        assert False, "Expected StepSkipped"
    except StepSkipped:
        pass


def test_transform_handler_maps_fields(test_db):
    """mapping={'out': '$in'} — payload['out'] set from payload['in']."""
    from infra.chain.steps import handle_transform
    step = {'id': 'step-1', 'config': {'mapping': {'out': '$in'}}}
    result = handle_transform(step, {'in': 'hello'})
    assert result['out'] == 'hello'
    assert result['in'] == 'hello'


def test_spawn_chain_handler_returns_id(test_db):
    """Mock create_chain_fn — payload has 'spawned_chain_id'."""
    from infra.chain.steps import handle_spawn_chain
    mock_create = lambda template_name, payload_ref=None: {'id': 'child-123'}
    step = {'id': 'step-1', 'config': {'template_name': 'child_template'}}
    result = handle_spawn_chain(step, {'x': 1}, mock_create)
    assert result['spawned_chain_id'] == 'child-123'


def test_approval_wait_raises_skipped(test_db):
    """handle_approval_wait always raises StepSkipped."""
    from infra.chain.steps import handle_approval_wait, StepSkipped
    step = {'id': 'step-1', 'config': {}}
    try:
        handle_approval_wait(step, {})
        assert False, "Expected StepSkipped"
    except StepSkipped:
        pass


# --- run_all shim for verify.py ---

TESTS = [
    ("runner_completes_simple_chain", test_runner_completes_simple_chain),
    ("runner_resumes_from_current_step", test_runner_resumes_from_current_step),
    ("runner_skips_complete_chain", test_runner_skips_complete_chain),
    ("runner_skips_failed_chain", test_runner_skips_failed_chain),
    ("runner_persists_after_each_step", test_runner_persists_after_each_step),
    ("runner_marks_chain_failed_on_step_error", test_runner_marks_chain_failed_on_step_error),
    ("runner_pauses_on_step_skipped", test_runner_pauses_on_step_skipped),
    ("runner_unknown_step_type_fails_chain", test_runner_unknown_step_type_fails_chain),
    ("payload_persisted_for_each_step", test_payload_persisted_for_each_step),
    ("tool_call_handler_executes_tool", test_tool_call_handler_executes_tool),
    ("tool_call_handler_missing_tool", test_tool_call_handler_missing_tool),
    ("tool_call_handler_resolves_args", test_tool_call_handler_resolves_args),
    ("llm_call_handler_calls_model", test_llm_call_handler_calls_model),
    ("llm_call_handler_resolves_template", test_llm_call_handler_resolves_template),
    ("condition_check_eq_true", test_condition_check_eq_true),
    ("condition_check_eq_false", test_condition_check_eq_false),
    ("condition_check_skip_if_false", test_condition_check_skip_if_false),
    ("transform_handler_maps_fields", test_transform_handler_maps_fields),
    ("spawn_chain_handler_returns_id", test_spawn_chain_handler_returns_id),
    ("approval_wait_raises_skipped", test_approval_wait_raises_skipped),
]


def run_all() -> tuple[int, int]:
    import infra.db.schema as _schema
    passed = failed = 0
    for name, fn in TESTS:
        _schema.init_db(":memory:")
        conn = _schema._conn
        try:
            fn(conn)
            print(f"  \u2713 chain_runner: {name}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 chain_runner: {name}: {e}")
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
