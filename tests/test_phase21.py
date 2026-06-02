"""
Phase 21 tests: Pydantic schemas, model router, agent_step, loop_back.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.chain.schemas import (
    BasePayload, RFDFrame, TextDraftPayload, DataStatsPayload,
    DataResearchPayload, ActionApprovalPayload, AgentDecisionPayload,
    validate_payload, PAYLOAD_SCHEMAS
)
from infra.model_router import get_model_for_role, route, get_today_spend
from infra.chain.steps import handle_agent_step, handle_loop_back, StepLoopBack, StepError
from infra.db.payloads import create_payload
from infra.db.budget_tracking import get_warning_sent_today, mark_warning_sent
from unittest.mock import patch, MagicMock
import pytest


# Pydantic schema tests

def test_text_draft_payload_valid():
    """TextDraftPayload with required fields — validates, word_count computed."""
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


def test_text_draft_payload_missing_required():
    """Missing title — raises ValidationError."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        TextDraftPayload(
            chain_id="test-chain",
            payload_type="text/draft",
            body="No title here",
            layer="technical"
        )


def test_rfd_frame_complete():
    """All 5 slots filled — is_complete() True."""
    frame = RFDFrame(
        moment="A moment",
        surprise="A surprise",
        struggle="A struggle",
        lesson="A lesson",
        next="Next step"
    )
    assert frame.is_complete() is True


def test_rfd_frame_incomplete():
    """One slot empty — is_complete() False."""
    frame = RFDFrame(
        moment="A moment",
        surprise="A surprise",
        struggle="A struggle",
        lesson="",
        next="Next step"
    )
    assert frame.is_complete() is False


def test_data_stats_payload():
    """DataStatsPayload round-trips through to_db_dict/from_db_dict."""
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


def test_validate_payload_unknown_type():
    """Unknown type — returns BasePayload, no error."""
    result = validate_payload("unknown_type", {"chain_id": "test", "foo": "bar"})
    assert isinstance(result, BasePayload)
    assert result.chain_id == "test"
    assert result.foo == "bar"


def test_validate_payload_known_type():
    """'text/draft' — returns TextDraftPayload instance."""
    result = validate_payload("text/draft", {
        "chain_id": "test",
        "title": "Test",
        "body": "Content",
        "layer": "technical"
    })
    assert isinstance(result, TextDraftPayload)
    assert result.title == "Test"


# Router tests

@patch('infra.model_router._get_daily_spent')
def test_router_free_model_first(mock_spent):
    """Role 'fast_intent' — first candidate is free tier."""
    mock_spent.return_value = 0.0
    models = get_model_for_role('fast_intent')
    assert len(models) > 0
    assert models[0]['tier'] == 'free'


@patch('infra.model_router._get_daily_spent')
def test_router_skips_paid_at_cap(mock_spent):
    """Budget at cap — paid models skipped, free used."""
    mock_spent.return_value = 0.30  # Over $0.25 cap
    
    def mock_call_fn(model, provider, prompt, **kwargs):
        return f"Response from {model}"
    
    # Should skip paid models and use free ones
    result = route('reasoning', mock_call_fn, "test prompt")
    assert 'result' in result
    assert 'model_used' in result


@patch('infra.model_router._get_daily_spent')
def test_router_raises_if_all_fail(mock_spent):
    """All models fail — raises RuntimeError."""
    mock_spent.return_value = 0.0
    
    def failing_call_fn(model, provider, prompt, **kwargs):
        raise Exception("All failed")
    
    with pytest.raises(RuntimeError):
        route('reasoning', failing_call_fn, "test prompt")


@patch('infra.model_router._get_daily_spent')
@patch('infra.model_router._record_spend')
def test_router_records_spend(mock_record, mock_spent):
    """Paid model call — cost recorded to budget tracker."""
    mock_spent.return_value = 0.0
    
    def mock_call_fn(model, provider, prompt, **kwargs):
        return "Response"
    
    route('reasoning', mock_call_fn, "test prompt")
    # Should have called _record_spend at least once
    assert mock_record.called


def test_get_today_spend_structure():
    """Returns dict with spent_usd, cap_usd, remaining_usd."""
    with patch('infra.model_router._get_daily_spent', return_value=0.10):
        spend = get_today_spend()
        assert 'spent_usd' in spend
        assert 'cap_usd' in spend
        assert 'remaining_usd' in spend
        assert 'at_warning' in spend
        assert 'at_cap' in spend
        assert 'percent_used' in spend


# Agent step tests

def test_agent_step_returns_decision():
    """Mock LLM returns valid JSON — payload has agent_decision."""
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


def test_agent_step_invalid_json():
    """Mock LLM returns garbage — raises StepError."""
    step = {
        'id': 'step-1',
        'config': {'role': 'reasoning', 'available_tools': [], 'context_fields': []}
    }
    payload = {}
    
    def mock_call_fn(prompt, role):
        return "not json at all"
    
    with pytest.raises(StepError):
        handle_agent_step(step, payload, mock_call_fn)


def test_agent_step_invalid_action():
    """Mock LLM returns unknown action — raises StepError."""
    step = {
        'id': 'step-1',
        'config': {'role': 'reasoning', 'available_tools': [], 'context_fields': []}
    }
    payload = {}
    
    def mock_call_fn(prompt, role):
        return '{"action": "invalid_action", "target": null, "args": {}, "reasoning": "test"}'
    
    with pytest.raises(StepError):
        handle_agent_step(step, payload, mock_call_fn)


def test_agent_step_with_markdown_fences():
    """Mock LLM returns JSON in markdown fences — strips and parses."""
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

def test_loop_back_raises_step_loop_back():
    """Condition met — raises StepLoopBack with correct anchor."""
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
    
    with pytest.raises(StepLoopBack) as exc_info:
        handle_loop_back(step, payload)
    
    assert exc_info.value.anchor_step_name == 'research'
    assert exc_info.value.iteration == 1


def test_loop_back_pass_through():
    """Condition not met — returns payload with loop_skipped=True."""
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


def test_loop_back_exceeds_max():
    """loop_count >= max_iterations — raises StepError."""
    step = {
        'id': 'step-1',
        'config': {
            'anchor_step_name': 'research',
            'max_iterations': 2
        }
    }
    payload = {'_loop_count_research': 2}
    
    with pytest.raises(StepError):
        handle_loop_back(step, payload)


def test_loop_back_missing_anchor():
    """No anchor_step_name — raises StepError."""
    step = {
        'id': 'step-1',
        'config': {}
    }
    payload = {}
    
    with pytest.raises(StepError):
        handle_loop_back(step, payload)


# Runner integration tests (simplified)

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

@patch('infra.db.payloads._exec')
def test_create_payload_validates(mock_exec):
    """create_payload with text/draft type — Pydantic validates."""
    # Mock the DB operations
    mock_exec.return_value.fetchone.return_value = {
        'id': 'payload-1',
        'data': '{"chain_id":"test","title":"Test"}'
    }
    
    # This should not raise an error
    result = create_payload(
        chain_id="test-chain",
        payload_type="text/draft",
        data={"title": "Test", "body": "Content", "layer": "technical"}
    )
    assert result is not None


@patch('infra.db.payloads._exec')
def test_create_payload_fallback_on_error(mock_exec):
    """Invalid payload data — falls back gracefully, no crash."""
    # Mock the DB operations
    mock_exec.return_value.fetchone.return_value = {
        'id': 'payload-1',
        'data': '{"chain_id":"test"}'
    }
    
    # Missing required field should log warning but not crash
    result = create_payload(
        chain_id="test-chain",
        payload_type="text/draft",
        data={"body": "Content", "layer": "technical"}  # Missing title
    )
    assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
