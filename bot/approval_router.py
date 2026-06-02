"""
Approval reply router.
Matches inbound Telegram callback_data to waiting approval listeners.
Resumes or fails the chain accordingly.
"""
import logging
from infra.chain.approval import get_listener, resolve_listener
from infra.db.chains import get_chain, update_chain_status

logger = logging.getLogger(__name__)

CALLBACK_PREFIX = "approval:"


def is_approval_callback(callback_data: str) -> bool:
    """Return True if this callback is an approval response."""
    return callback_data.startswith(CALLBACK_PREFIX)


def parse_callback(callback_data: str) -> tuple[str, str] | None:
    """
    Parse callback_data into (action, listener_id).
    Returns None if format is invalid.
    Expected format: 'approval:{action}:{listener_id}'
    """
    parts = callback_data.split(":")
    if len(parts) != 3 or parts[0] != "approval":
        return None
    return parts[1], parts[2]


def _build_resume_fn():
    """Build the resume function for ChainRunner."""
    def resume_chain(chain_id: str):
        from infra.db.chains import get_chain
        from infra.chain.runner import ChainRunner
        from infra.chain.template_loader import load_template, TemplateError
        from tools.registry import TOOL_REGISTRY

        chain = get_chain(chain_id)
        if not chain:
            return
        try:
            template = load_template(chain['template_name'])
        except TemplateError as e:
            logger.error(f"Failed to load template {chain['template_name']}: {e}")
            return
        runner = ChainRunner(tool_registry=TOOL_REGISTRY)
        runner.run(chain_id, template['steps'])
    return resume_chain


def handle_approval_callback(callback_data: str,
                              message_id: str = None,
                              resume_chain_fn=None) -> dict:
    """
    Handle an inbound approval callback.

    callback_data: the raw callback_data from Telegram
    message_id: Telegram message ID for the approval message
    resume_chain_fn: callable(chain_id, step_definitions) to resume
                     the chain — injected by caller

    Returns dict with keys: status, chain_id, action, message
    """
    parsed = parse_callback(callback_data)
    if parsed is None:
        return {
            "status": "error",
            "message": f"Invalid callback format: {callback_data}"
        }

    action, listener_id = parsed
    listener = get_listener(listener_id)

    if listener is None:
        return {
            "status": "error",
            "message": f"Listener not found: {listener_id}"
        }

    if listener['status'] == 'resolved':
        return {
            "status": "already_resolved",
            "chain_id": listener['chain_id'],
            "message": "This approval was already handled."
        }

    chain_id = listener['chain_id']
    chain = get_chain(chain_id)

    if chain is None:
        resolve_listener(listener_id, 'expired', message_id)
        return {
            "status": "error",
            "message": f"Chain not found: {chain_id}"
        }

    if action == 'approve':
        resolve_listener(listener_id, 'approved', message_id)
        # Advance chain past the approval step
        update_chain_status(chain_id, 'running',
                            current_step=chain['current_step'] + 1)
        logger.info(f"Approval granted for chain {chain_id} "
                    f"by listener {listener_id}")

        if resume_chain_fn is None:
            resume_chain_fn = _build_resume_fn()
        try:
            resume_chain_fn(chain_id)
        except Exception as e:
            logger.error(f"Chain resume failed for {chain_id}: {e}")
            return {
                "status": "resume_failed",
                "chain_id": chain_id,
                "message": f"Approved but resume failed: {e}"
            }

        return {
            "status": "approved",
            "chain_id": chain_id,
            "message": "✅ Approved. Chain resumed."
        }

    elif action == 'reject':
        resolve_listener(listener_id, 'rejected', message_id)
        update_chain_status(chain_id, 'failed')
        logger.info(f"Approval rejected for chain {chain_id}")
        return {
            "status": "rejected",
            "chain_id": chain_id,
            "message": "❌ Rejected. Chain stopped."
        }

    else:
        return {
            "status": "error",
            "message": f"Unknown action: {action}"
        }
