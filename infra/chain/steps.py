"""
Step type handlers for the chain runner.
Each handler: (step: dict, payload: dict) -> dict
Returns updated payload dict on success.
Raises StepError on unrecoverable failure.
"""
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class StepError(Exception):
    """Raised when a step fails unrecoverably."""
    pass


class StepSkipped(Exception):
    """Raised when a step is intentionally skipped."""
    pass


def handle_tool_call(step: dict, payload: dict,
                     tool_registry: dict) -> dict:
    """
    Execute a tool from the registry.
    step config requires: tool_name, tool_args (dict, may reference
    payload fields via '{field}' placeholders).
    Returns payload enriched with tool result under key 'tool_result'.
    """
    config = step.get('config', {})
    tool_name = config.get('tool_name')
    if not tool_name:
        raise StepError(f"tool_call step missing tool_name: {step['id']}")
    if tool_name not in tool_registry:
        raise StepError(f"tool '{tool_name}' not in registry")

    tool_fn = tool_registry[tool_name]
    tool_args = _resolve_args(config.get('tool_args', {}), payload)

    try:
        result = tool_fn(**tool_args)
    except Exception as e:
        raise StepError(f"tool '{tool_name}' raised: {e}") from e

    return {**payload, 'tool_result': result}


def handle_llm_call(step: dict, payload: dict,
                    call_model_fn: Callable) -> dict:
    """
    Call the LLM with a prompt template resolved against payload.
    step config requires: prompt_template, model_role (default: 'reasoning').
    Returns payload enriched with 'llm_result'.
    """
    config = step.get('config', {})
    prompt_template = config.get('prompt_template', '')
    model_role = config.get('model_role', 'reasoning')

    prompt = _resolve_template(prompt_template, payload)

    try:
        result = call_model_fn(prompt=prompt, role=model_role)
    except Exception as e:
        raise StepError(f"llm_call failed: {e}") from e

    return {**payload, 'llm_result': result}


def handle_condition_check(step: dict, payload: dict) -> dict:
    """
    Evaluate a condition against the payload.
    step config requires: field, operator, value.
    Operators: eq, neq, gt, lt, gte, lte, contains, exists.
    Returns payload with 'condition_result' (bool) and 'condition_met' (bool).
    Raises StepSkipped if condition not met and skip_if_false=True.
    """
    config = step.get('config', {})
    field = config.get('field', '')
    operator = config.get('operator', 'exists')
    value = config.get('value')
    skip_if_false = config.get('skip_if_false', False)

    field_value = _get_nested(payload, field)
    result = _evaluate(field_value, operator, value)

    updated = {**payload, 'condition_result': result, 'condition_met': result}

    if not result and skip_if_false:
        raise StepSkipped(f"Condition '{field} {operator} {value}' not met")

    return updated


def handle_transform(step: dict, payload: dict) -> dict:
    """
    Reshape payload fields.
    step config requires: mapping (dict of output_key -> input_key or
    literal value). Produces a new payload from the mapping.
    Preserves all existing payload fields unless overwritten.
    """
    config = step.get('config', {})
    mapping = config.get('mapping', {})

    updates = {}
    for out_key, in_key in mapping.items():
        if isinstance(in_key, str) and in_key.startswith('$'):
            updates[out_key] = _get_nested(payload, in_key[1:])
        else:
            updates[out_key] = in_key

    return {**payload, **updates}


def handle_spawn_chain(step: dict, payload: dict,
                       create_chain_fn: Callable) -> dict:
    """
    Instantiate a new child chain from a template name.
    step config requires: template_name.
    Returns payload with 'spawned_chain_id'.
    """
    config = step.get('config', {})
    template_name = config.get('template_name')
    if not template_name:
        raise StepError(f"spawn_chain step missing template_name: {step['id']}")

    try:
        child_chain = create_chain_fn(template_name=template_name,
                                      payload_ref=payload.get('id'))
    except Exception as e:
        raise StepError(f"spawn_chain failed to create chain: {e}") from e

    return {**payload, 'spawned_chain_id': child_chain['id']}


def handle_approval_wait(step: dict, payload: dict,
                         send_approval_fn: Callable = None) -> dict:
    """
    Pause the chain and send an approval request to Telegram.
    Creates an approval_listeners row.
    Calls send_approval_fn(message_dict, chat_id) to deliver the message.
    Always raises StepSkipped — the chain resumes via the reply router.

    step config requires:
      telegram_chat_id: str — where to send the approval request
      summary_field: str — payload field to use as the approval summary
                           (defaults to showing payload keys)
    send_approval_fn: callable(message_dict, chat_id) — injected by runner
    """
    from infra.chain.approval import create_listener, build_approval_message

    config = step.get('config', {})
    chat_id = config.get('telegram_chat_id')
    summary_field = config.get('summary_field')

    if not chat_id:
        raise StepError(
            f"approval_wait step missing telegram_chat_id: {step['id']}"
        )

    chain_id = step.get('chain_id', '')
    step_id = step.get('id', '')
    step_name = step.get('name', 'approval')

    # Build summary from payload
    if summary_field and summary_field in payload:
        summary = str(payload[summary_field])[:500]
    else:
        summary = f"Payload keys: {', '.join(payload.keys())}"

    listener = create_listener(
        chain_id=chain_id,
        step_id=step_id,
        telegram_chat_id=chat_id
    )

    message = build_approval_message(
        chain_id=chain_id,
        step_name=step_name,
        payload_summary=summary,
        listener_id=listener['id']
    )

    if send_approval_fn:
        try:
            send_approval_fn(message, chat_id)
        except Exception as e:
            # Log but don't fail — listener is created, message may
            # have been sent. Router can still resolve it.
            import logging
            logging.getLogger(__name__).warning(
                f"Approval message send failed: {e}"
            )

    raise StepSkipped(f"Waiting for approval: listener {listener['id']}")


# --- Helpers ---

def _resolve_args(args: dict, payload: dict) -> dict:
    """Replace '{field}' placeholders in arg values with payload values."""
    resolved = {}
    for k, v in args.items():
        if isinstance(v, str) and v.startswith('{') and v.endswith('}'):
            field = v[1:-1]
            resolved[k] = _get_nested(payload, field)
        else:
            resolved[k] = v
    return resolved


def _resolve_template(template: str, payload: dict) -> str:
    """Replace {field} placeholders in a prompt template."""
    try:
        return template.format(**payload)
    except KeyError:
        return template


def _get_nested(obj: dict, path: str):
    """Get nested dict value via dot notation. Returns None if missing."""
    parts = path.split('.')
    current = obj
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _evaluate(field_value, operator: str, value) -> bool:
    """Evaluate a condition. Returns bool."""
    if operator == 'exists':
        return field_value is not None
    if operator == 'eq':
        return field_value == value
    if operator == 'neq':
        return field_value != value
    if operator == 'gt':
        return field_value is not None and field_value > value
    if operator == 'lt':
        return field_value is not None and field_value < value
    if operator == 'gte':
        return field_value is not None and field_value >= value
    if operator == 'lte':
        return field_value is not None and field_value <= value
    if operator == 'contains':
        return value in (field_value or '')
    return False
