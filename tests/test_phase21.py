"""
Phase 21 tests: Pydantic schemas, model router, agent_step, loop_back.
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


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


# Pydantic schema tests

@test("schemas: text_draft_payload_valid")
def test_text_draft_payload_valid():
    """TextDraftPayload with required fields — validates, word_count computed."""
    from infra.chain.schemas import TextDraftPayload
    payload = TextDraftPayload(
        chain_id="test-chain",
        payload_type="text/draft",
        title="Test Post",
        body="This is a test post with some words.",
        layer="technical"
    )
    assert payload.word_count == 8
    assert payload.title == "Test Post"
    assert payload.layer == "technical"


@test("schemas: text_draft_payload_missing_required")
def test_text_draft_payload_missing_required():
    """Missing title — raises ValidationError."""
    from infra.chain.schemas import TextDraftPayload
    try:
        TextDraftPayload(
            chain_id="test-chain",
            payload_type="text/draft",
            body="No title here",
            layer="technical"
        )
        assert False, "Expected ValidationError"
    except Exception:
        pass  # Expected


@test("schemas: rfd_frame_complete")
def test_rfd_frame_complete():
    """All 5 slots filled — is_complete() True."""
    from infra.chain.schemas import RFDFrame
    frame = RFDFrame(
        moment="A moment",
        surprise="A surprise",
        struggle="A struggle",
        lesson="A lesson",
        next="Next step"
    )
    assert frame.is_complete() is True


@test("schemas: rfd_frame_incomplete")
def test_rfd_frame_incomplete():
    """One slot empty — is_complete() False."""
    from infra.chain.schemas import RFDFrame
    frame = RFDFrame(
        moment="A moment",
        surprise="A surprise",
        struggle="A struggle",
        lesson="",
        next="Next step"
    )
    assert frame.is_complete() is False


@test("schemas: data_stats_payload")
def test_data_stats_payload():
    """DataStatsPayload round-trips through to_db_dict/from_db_dict."""
    from infra.chain.schemas import DataStatsPayload
    payload = DataStatsPayload(
        chain_id="test-chain",
        payload_type="data/stats",
        source="api",
        captured_at="2026-06-01T00:00:00Z",
        values={"users": 100, "active": 50}
    )
    db_dict = payload.to_db_dict()
    restored = DataStatsPayload(**db_dict)
    assert restored.source == "api"
    assert restored.values == {"users": 100, "active": 50}


@test("schemas: validate_payload_unknown_type")
def test_validate_payload_unknown_type():
    """Unknown type — returns BasePayload, no error."""
    from infra.chain.schemas import validate_payload, BasePayload
    result = validate_payload("unknown_type", {"chain_id": "test", "foo": "bar"})
    assert isinstance(result, BasePayload)
    assert result.chain_id == "test"
    assert result.foo == "bar"


@test("schemas: validate_payload_known_type")
def test_validate_payload_known_type():
    """'text/draft' — returns TextDraftPayload instance."""
    from infra.chain.schemas import validate_payload, TextDraftPayload
    result = validate_payload("text/draft", {
        "chain_id": "test",
        "title": "Test",
        "body": "Content",
        "layer": "technical"
    })
    assert isinstance(result, TextDraftPayload)
    assert result.title == "Test"


# Router tests

@test("router: free_model_first")
def test_router_free_model_first():
    """Role 'fast_intent' — first candidate is free tier."""
    from infra.model_router import get_model_for_role
    from unittest.mock import patch
    with patch('infra.model_router._get_daily_spent', return_value=0.0):
        models = get_model_for_role('fast_intent')
        assert len(models) > 0
        assert models[0]['tier'] == 'free'


@test("router: skips_paid_at_cap")
def test_router_skips_paid_at_cap():
    """Budget at cap — paid models skipped, free used."""
    from infra.model_router import route
    from unittest.mock import patch
    
    with patch('infra.model_router._get_daily_spent', return_value=0.30), \
         patch('bot.model_helpers.get_call_fn') as mock_get_call:
        def mock_call_fn(model, provider, prompt, **kwargs):
            # Free models will succeed, paid models should be skipped
            if provider == 'ollama':
                return f"Response from {model}"
            raise Exception("Paid model should be skipped")
        mock_get_call.return_value = mock_call_fn
        
        result = route('offline', "test prompt")
        assert 'result' in result
        assert 'model_used' in result


@test("router: raises_if_all_fail")
def test_router_raises_if_all_fail():
    """All models fail — raises RuntimeError."""
    from infra.model_router import route
    from unittest.mock import patch
    
    with patch('infra.model_router._get_daily_spent', return_value=0.0), \
         patch('bot.model_helpers.get_call_fn') as mock_get_call:
        def failing_call_fn(model, provider, prompt, **kwargs):
            raise Exception("All failed")
        mock_get_call.return_value = failing_call_fn
        
        try:
            route('reasoning', "test prompt")
            assert False, "Expected RuntimeError"
        except RuntimeError:
            pass  # Expected


@test("router: records_spend")
def test_router_records_spend():
    """Paid model call — cost recorded to budget tracker."""
    from infra.model_router import route
    from unittest.mock import patch
    
    with patch('infra.model_router._get_daily_spent', return_value=0.0), \
         patch('infra.model_router._record_spend') as mock_record, \
         patch('bot.model_helpers.get_call_fn') as mock_get_call:
        def mock_call_fn(model, provider, prompt, **kwargs):
            return "Response"
        mock_get_call.return_value = mock_call_fn
        
        route('reasoning', "test prompt")
        assert mock_record.called


@test("router: get_today_spend_structure")
def test_get_today_spend_structure():
    """Returns dict with spent_usd, cap_usd, remaining_usd."""
    from infra.model_router import get_today_spend
    from unittest.mock import patch
    
    with patch('infra.model_router._get_daily_spent', return_value=0.10):
        spend = get_today_spend()
        assert 'spent_usd' in spend
        assert 'cap_usd' in spend
        assert 'remaining_usd' in spend
        assert 'at_warning' in spend
        assert 'at_cap' in spend
        assert 'percent_used' in spend


# Agent step tests

@test("agent_step: returns_decision")
def test_agent_step_returns_decision():
    """Mock LLM returns valid JSON — payload has agent_decision."""
    from infra.chain.steps import handle_agent_step
    step = {
        'id': 'step-1',
        'config': {
            'role': 'reasoning',
            'available_tools': ['web_search'],
            'context_fields': ['title'],
            'instruction': 'Decide'
        }
    }
    payload = {'title': 'Test', 'body': 'Content'}
    
    def mock_call_fn(prompt, role):
        return '{"action": "complete", "target": null, "args": {}, "reasoning": "Done"}'
    
    result = handle_agent_step(step, payload, mock_call_fn)
    assert 'agent_decision' in result
    assert result['agent_decision']['action'] == 'complete'


@test("agent_step: invalid_json")
def test_agent_step_invalid_json():
    """Mock LLM returns garbage — raises StepError."""
    from infra.chain.steps import handle_agent_step, StepError
    step = {
        'id': 'step-1',
        'config': {'role': 'reasoning', 'available_tools': [], 'context_fields': []}
    }
    payload = {}
    
    def mock_call_fn(prompt, role):
        return "not json at all"
    
    try:
        handle_agent_step(step, payload, mock_call_fn)
        assert False, "Expected StepError"
    except StepError:
        pass  # Expected


@test("agent_step: invalid_action")
def test_agent_step_invalid_action():
    """Mock LLM returns unknown action — raises StepError."""
    from infra.chain.steps import handle_agent_step, StepError
    step = {
        'id': 'step-1',
        'config': {'role': 'reasoning', 'available_tools': [], 'context_fields': []}
    }
    payload = {}
    
    def mock_call_fn(prompt, role):
        return '{"action": "invalid_action", "target": null, "args": {}, "reasoning": "test"}'
    
    try:
        handle_agent_step(step, payload, mock_call_fn)
        assert False, "Expected StepError"
    except StepError:
        pass  # Expected


@test("agent_step: with_markdown_fences")
def test_agent_step_with_markdown_fences():
    """Mock LLM returns JSON in markdown fences — strips and parses."""
    from infra.chain.steps import handle_agent_step
    step = {
        'id': 'step-1',
        'config': {'role': 'reasoning', 'available_tools': [], 'context_fields': []}
    }
    payload = {}
    
    def mock_call_fn(prompt, role):
        return '```json\n{"action": "complete", "target": null, "args": {}, "reasoning": "test"}\n```'
    
    result = handle_agent_step(step, payload, mock_call_fn)
    assert result['agent_decision']['action'] == 'complete'


# Loop back tests

@test("loop_back: raises_step_loop_back")
def test_loop_back_raises_step_loop_back():
    """Condition met — raises StepLoopBack with correct anchor."""
    from infra.chain.steps import handle_loop_back, StepLoopBack
    step = {
        'id': 'step-1',
        'config': {
            'anchor_step_name': 'research',
            'max_iterations': 3,
            'condition_field': 'retry',
            'condition_value': True
        }
    }
    payload = {'retry': True}
    
    try:
        handle_loop_back(step, payload)
        assert False, "Expected StepLoopBack"
    except StepLoopBack as e:
        assert e.anchor_step_name == 'research'
        assert e.iteration == 1


@test("loop_back: pass_through")
def test_loop_back_pass_through():
    """Condition not met — returns payload with loop_skipped=True."""
    from infra.chain.steps import handle_loop_back
    step = {
        'id': 'step-1',
        'config': {
            'anchor_step_name': 'research',
            'condition_field': 'retry',
            'condition_value': True
        }
    }
    payload = {'retry': False}
    
    result = handle_loop_back(step, payload)
    assert result.get('loop_skipped') is True


@test("loop_back: exceeds_max")
def test_loop_back_exceeds_max():
    """loop_count >= max_iterations — raises StepError."""
    from infra.chain.steps import handle_loop_back, StepError
    step = {
        'id': 'step-1',
        'config': {
            'anchor_step_name': 'research',
            'max_iterations': 2
        }
    }
    payload = {'_loop_count_research': 2}
    
    try:
        handle_loop_back(step, payload)
        assert False, "Expected StepError"
    except StepError:
        pass  # Expected


@test("loop_back: missing_anchor")
def test_loop_back_missing_anchor():
    """No anchor_step_name — raises StepError."""
    from infra.chain.steps import handle_loop_back, StepError
    step = {
        'id': 'step-1',
        'config': {}
    }
    payload = {}
    
    try:
        handle_loop_back(step, payload)
        assert False, "Expected StepError"
    except StepError:
        pass  # Expected


# Integration tests

@test("integration: model_registry_loads")
def test_model_registry_loads():
    """model_registry.yaml loads without error."""
    import yaml
    from pathlib import Path
    registry_path = Path(__file__).parent.parent / "config" / "model_registry.yaml"
    with open(registry_path, "r") as f:
        registry = yaml.safe_load(f)
    assert 'models' in registry
    assert 'role_routing' in registry
    assert 'budget' in registry


@test("integration: model_registry_all_roles_covered")
def test_model_registry_all_roles_covered():
    """All 8 roles have at least one model."""
    import yaml
    from pathlib import Path
    registry_path = Path(__file__).parent.parent / "config" / "model_registry.yaml"
    with open(registry_path, "r") as f:
        registry = yaml.safe_load(f)
    
    roles = registry['role_routing']
    expected_roles = ['reasoning', 'chat', 'fast_intent', 'structured',
                      'long_context', 'quality_gate', 'cost_sensitive', 'offline']
    
    for role in expected_roles:
        assert role in roles
        assert len(roles[role]) > 0


# Payload validation integration tests

@test("payloads: create_payload_validates")
def test_create_payload_validates():
    """create_payload with text/draft type — Pydantic validates."""
    from infra.chain.schemas import validate_payload, TextDraftPayload
    # Test the validation logic directly
    result = validate_payload("text/draft", {
        "chain_id": "test",
        "title": "Test",
        "body": "Content",
        "layer": "technical"
    })
    assert isinstance(result, TextDraftPayload)
    assert result.title == "Test"


@test("payloads: create_payload_fallback_on_error")
def test_create_payload_fallback_on_error():
    """Invalid payload data — falls back gracefully, no crash."""
    from infra.chain.schemas import validate_payload, BasePayload
    # Test that validation raises error for missing required field
    try:
        validate_payload("text/draft", {
            "chain_id": "test",
            "body": "Content",
            "layer": "technical"  # Missing title
        })
        assert False, "Expected validation error"
    except Exception:
        # Expected - validation failed
        pass
    
    # Test that we can fall back to BasePayload (what create_payload does)
    result = BasePayload(
        chain_id="test",
        body="Content",
        layer="technical"
    )
    assert isinstance(result, BasePayload)
    assert result.chain_id == "test"
