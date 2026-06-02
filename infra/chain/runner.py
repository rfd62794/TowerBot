"""
Chain runner — execution engine for the chain system.
Reads chain state, executes steps, persists after every step.
Resumable: on restart, reads current_step and continues from there.
"""
import logging
from typing import Callable

from infra.db.chains import (
    get_chain, update_chain_status, append_step,
    update_step, get_steps_for_chain
)
from infra.db.payloads import create_payload, get_payload
from infra.chain.steps import (
    StepError, StepSkipped,
    handle_tool_call, handle_llm_call, handle_condition_check,
    handle_transform, handle_spawn_chain, handle_approval_wait
)

logger = logging.getLogger(__name__)

STEP_HANDLERS = {
    'tool_call':       handle_tool_call,
    'llm_call':        handle_llm_call,
    'condition_check': handle_condition_check,
    'transform':       handle_transform,
    'spawn_chain':     handle_spawn_chain,
    'approval_wait':   handle_approval_wait,
}


class ChainRunner:
    """
    Executes a chain step by step. Persists state after every step.
    Inject dependencies via constructor — no global imports of LLM or
    tool registry inside this class.
    """

    def __init__(self,
                 tool_registry: dict = None,
                 call_model_fn: Callable = None,
                 create_chain_fn: Callable = None):
        self.tool_registry = tool_registry or {}
        self.call_model_fn = call_model_fn or self._noop_model
        self.create_chain_fn = create_chain_fn or self._noop_spawn

    def run(self, chain_id: str, step_definitions: list[dict]) -> dict:
        """
        Execute a chain to completion or until paused/failed.

        step_definitions: list of step config dicts. Each must have:
          - name (str)
          - type (str) — one of the STEP_HANDLERS keys
          - config (dict) — step-type-specific config

        Returns final chain dict from DB.
        """
        chain = get_chain(chain_id)
        if chain is None:
            raise ValueError(f"Chain not found: {chain_id}")

        if chain['status'] in ('complete', 'failed'):
            logger.info(f"Chain {chain_id} already {chain['status']} — skipping")
            return chain

        # Load or initialize current payload
        payload = {}
        if chain.get('payload_ref'):
            p = get_payload(chain['payload_ref'])
            if p:
                payload = p['data']

        start_index = chain['current_step']
        steps_to_run = step_definitions[start_index:]

        for i, step_def in enumerate(steps_to_run):
            global_index = start_index + i
            step_type = step_def.get('type', 'unknown')
            step_name = step_def.get('name', f'step_{global_index}')
            step_config = step_def.get('config', {})

            # Append step record
            step = append_step(
                chain_id=chain_id,
                step_index=global_index,
                step_type=step_type,
                name=step_name
            )
            step['config'] = step_config

            # Mark step running and update chain position
            update_step(step['id'], status='running')
            update_chain_status(chain_id, 'running',
                                current_step=global_index)

            # Create input payload snapshot
            input_payload = create_payload(
                chain_id, 'step_input', payload,
                step_id=step['id']
            )
            update_step(step['id'], status='running',
                        input_payload_id=input_payload['id'])

            handler = STEP_HANDLERS.get(step_type)
            if handler is None:
                update_step(step['id'], status='failed',
                            error=f"Unknown step type: {step_type}")
                update_chain_status(chain_id, 'failed')
                logger.error(f"Unknown step type '{step_type}' in chain {chain_id}")
                return get_chain(chain_id)

            try:
                if step_type == 'tool_call':
                    payload = handler(step, payload, self.tool_registry)
                elif step_type == 'llm_call':
                    payload = handler(step, payload, self.call_model_fn)
                elif step_type == 'spawn_chain':
                    payload = handler(step, payload, self.create_chain_fn)
                else:
                    payload = handler(step, payload)

            except StepSkipped as e:
                output_payload = create_payload(
                    chain_id, 'step_output', payload,
                    step_id=step['id']
                )
                update_step(step['id'], status='skipped',
                            output_payload_id=output_payload['id'])
                update_chain_status(chain_id, 'waiting_approval',
                                    current_step=global_index)
                logger.info(f"Chain {chain_id} paused at step {global_index}: {e}")
                return get_chain(chain_id)

            except StepError as e:
                update_step(step['id'], status='failed', error=str(e))
                update_chain_status(chain_id, 'failed')
                logger.error(f"Chain {chain_id} failed at step {global_index}: {e}")
                return get_chain(chain_id)

            except Exception as e:
                update_step(step['id'], status='failed',
                            error=f"Unexpected: {e}")
                update_chain_status(chain_id, 'failed')
                logger.error(f"Chain {chain_id} unexpected error at step "
                             f"{global_index}: {e}", exc_info=True)
                return get_chain(chain_id)

            # Step succeeded — persist output
            output_payload = create_payload(
                chain_id, 'step_output', payload,
                step_id=step['id']
            )
            update_step(step['id'], status='complete',
                        output_payload_id=output_payload['id'])
            logger.info(f"Chain {chain_id} step {global_index} "
                        f"'{step_name}' complete")

        # All steps complete
        update_chain_status(chain_id, 'complete',
                            current_step=len(step_definitions))
        logger.info(f"Chain {chain_id} complete")
        return get_chain(chain_id)

    @staticmethod
    def _noop_model(prompt: str, role: str = 'reasoning') -> str:
        """Fallback model fn when none injected."""
        return f"[no model configured — prompt was: {prompt[:50]}]"

    @staticmethod
    def _noop_spawn(template_name: str, payload_ref: str = None) -> dict:
        """Fallback spawn fn when none injected."""
        return {'id': f'noop-{template_name}'}
