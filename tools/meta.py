"""
tools/meta.py

Meta-tools that help the agent reason.
No API calls. No caching. No stale data.
Simple passthrough functions only.
"""


def think(thought: str) -> dict:
    """
    Record a reasoning step before acting.
    Creates a visible scratchpad entry.

    Provides context continuity when
    models switch due to throttling —
    the next model sees the thought
    and can continue from it.

    Returns immediately. No side effects.
    """
    return {
        "ok": True,
        "thought": thought,
        "stale_notice": None
    }
