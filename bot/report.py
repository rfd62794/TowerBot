"""Layer 3 — Report.

Centralized event surfacing. Every memory op, tool call, and error
announces itself here. Decoupled from PTB: the Telegram send is an
async callback injected at startup. Fire-and-forget, never raises.
"""

import asyncio
import logging

logger = logging.getLogger("privy.report")

_send_callback = None


def init_report(send_fn) -> None:
    """Register the async send function: `async def send(text: str) -> None`."""
    global _send_callback
    _send_callback = send_fn


def _format(event_type: str, kwargs: dict):
    """Return the Telegram text for an event, or None if it should stay silent."""
    if event_type == "memory_saved":
        return f"📝 Noted [{kwargs.get('layer')}]: {kwargs.get('content')}"
    if event_type == "memory_updated":
        return f"✏️ Updated [{kwargs.get('key')}]: {kwargs.get('reason')}"
    if event_type == "memory_retired":
        return f"🗄️ Retired [{kwargs.get('key')}]: {kwargs.get('reason')}"
    if event_type == "memory_retrieved":
        if kwargs.get("count", 0) == 0:
            return None
        return (
            f"🔍 Retrieved {kwargs.get('count')} "
            f"for '{kwargs.get('query')}': {kwargs.get('keys')}"
        )
    if event_type == "thread_named":
        return f"📎 Thread: {kwargs.get('name')}"
    if event_type == "thread_new":
        return None  # typing indicator already signals receipt
    if event_type == "commitment_saved":
        deadline = kwargs.get("deadline") or "no deadline set"
        return f"📋 Commitment: {kwargs.get('description')}\nDue: {deadline}"
    if event_type == "tool_called":
        return f"🔧 Tool: {kwargs.get('tool_name')}"
    if event_type == "error":
        return f"🔴 Error: {kwargs.get('message')}"
    if event_type == "model_routed":
        return None  # log only, never surfaces
    if event_type == "thought":
        thought = kwargs.get("thought", "")
        if not thought:
            return None
        return f"💭 {thought}"
    return None


async def report(event_type: str, **kwargs) -> None:
    """Format an event and surface it via the injected send callback."""
    try:
        logger.info("event=%s %s", event_type, kwargs)
        text = _format(event_type, kwargs)
        if text is None:
            return
        if _send_callback is None:
            logger.warning("no send callback registered; would send: %s", text)
            return
        await _send_callback(text)
    except Exception as e:
        logger.error("report failed for %s: %s", event_type, e)
