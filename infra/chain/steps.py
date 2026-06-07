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


class StepLoopBack(Exception):
    """
    Raised when a loop_back step triggers.
    Carries the anchor step name to loop back to.
    Not a failure — a deliberate redirect.
    """
    def __init__(self, anchor_step_name: str, iteration: int):
        self.anchor_step_name = anchor_step_name
        self.iteration = iteration
        super().__init__(
            f"Loop back to '{anchor_step_name}' (iteration {iteration})"
        )


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

    result_key = config.get('result_key', 'tool_result')
    updated = {**payload, 'tool_result': result, result_key: result}
    return updated


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


def handle_agent_step(step: dict, payload: dict,
                      call_model_fn: Callable) -> dict:
    """
    Reasoning step — model examines current chain context and decides
    what to do next. Returns payload with 'agent_decision' dict.

    The model receives:
    - Current payload summary
    - Available actions: call_tool, llm_call, complete, loop_back, fail
    - Step config constraints

    step config:
      role: model role to use (default: 'reasoning')
      available_tools: list of tool names the agent can reference
      context_fields: list of payload fields to include in context
      instruction: specific guidance for this decision point

    Returns payload enriched with:
      agent_decision: {action, target, args, reasoning}
    """
    config = step.get('config', {})
    role = config.get('role', 'reasoning')
    available_tools = config.get('available_tools', [])
    context_fields = config.get('context_fields', [])
    instruction = config.get('instruction', 'Decide the next action.')

    # Build context from payload fields
    context = {k: payload.get(k) for k in context_fields if k in payload}

    prompt = f"""You are deciding the next action in a chain.

Current context:
{context}

Available actions:
- call_tool: call a specific tool. Specify target (tool name) and args.
- llm_call: run a language model step. Specify target (role) and args.
- loop_back: retry from an earlier step. Specify target (step name).
- complete: chain is done. No target needed.
- fail: unrecoverable error. Specify reasoning.

Available tools: {available_tools}

Instruction: {instruction}

Respond with a JSON object only:
{{
    "action": "call_tool|llm_call|complete|loop_back|fail",
    "target": "tool_name_or_step_name_or_null",
    "args": {{}},
    "reasoning": "brief explanation"
}}"""

    try:
        raw = call_model_fn(prompt=prompt, role=role)
        import json
        # Strip markdown fences if present
        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1])
        decision = json.loads(clean)
    except Exception as e:
        raise StepError(f"agent_step failed to parse decision: {e}")

    valid_actions = {"call_tool", "llm_call", "complete", "loop_back", "fail"}
    if decision.get("action") not in valid_actions:
        raise StepError(
            f"agent_step returned invalid action: {decision.get('action')}"
        )

    return {**payload, "agent_decision": decision}


def handle_loop_back(step: dict, payload: dict) -> dict:
    """
    Loop back to an earlier step.
    Raises StepLoopBack — runner catches and resets current_step.

    step config:
      anchor_step_name: str — name of step to loop back to
      max_iterations: int — default 3, hard ceiling
      condition_field: str — optional payload field to check
      condition_value: any — if condition_field equals this, loop;
                             else pass through (no loop)
    """
    config = step.get('config', {})
    anchor = config.get('anchor_step_name')
    max_iter = config.get('max_iterations', 3)
    condition_field = config.get('condition_field')
    condition_value = config.get('condition_value')

    if not anchor:
        raise StepError("loop_back step missing anchor_step_name")

    # Check condition if specified
    if condition_field is not None:
        field_val = payload.get(condition_field)
        if field_val != condition_value:
            # Condition not met — pass through, no loop
            return {**payload, "loop_skipped": True}

    # Check iteration count from payload
    loop_key = f"_loop_count_{anchor}"
    current_count = payload.get(loop_key, 0)

    if current_count >= max_iter:
        raise StepError(
            f"loop_back exceeded max_iterations ({max_iter}) "
            f"for anchor '{anchor}'"
        )

    updated_payload = {
        **payload,
        loop_key: current_count + 1
    }

    raise StepLoopBack(
        anchor_step_name=anchor,
        iteration=current_count + 1
    )


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
