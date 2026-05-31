"""Tests for transport-layer helpers — message chunking and thinking thread."""

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Skip tests if OpenAI credentials not available (bot.agent initializes client at module level)
if not os.getenv("OPENAI_API_KEY") and not os.getenv("OPENAI_ADMIN_KEY"):
    print("  ⚠ transport: skipped (OPENAI_API_KEY not set)")
    def run_all() -> tuple[int, int]:
        return 0, 0
    sys.exit(0)

from bot.transport import _chunk_message, _thinking_thread


def test_chunk_message_single_chunk_under_limit():
    """Text under limit returns as single-element list unchanged."""
    text = "hello world"
    chunks = _chunk_message(text)
    assert chunks == [text]


def test_chunk_message_splits_at_newline():
    """Text over limit splits at last newline before max_len."""
    first = "a" * 3990
    second = "extra content here"
    text = first + "\n" + second
    chunks = _chunk_message(text)
    assert len(chunks) == 2
    assert chunks[0] == first
    assert chunks[1] == second


def test_chunk_message_splits_at_limit_when_no_newline():
    """Text over limit with no newline splits at exactly max_len."""
    text = "a" * 5000
    chunks = _chunk_message(text)
    assert len(chunks) == 2
    assert len(chunks[0]) == 4000
    assert chunks[1] == "a" * 1000


def test_thinking_thread_skips_on_fast_response():
    """stop_event set before 2s grace — send_message never called."""
    bot = MagicMock()
    bot.send_message = AsyncMock()

    async def _run():
        stop = asyncio.Event()
        stop.set()  # already done before thread even starts
        await _thinking_thread(12345, bot, stop)

    asyncio.run(_run())
    bot.send_message.assert_not_called()


def test_thinking_thread_sends_and_rotates():
    """After 2s send_message fires; after another 3s edit_message_text fires."""
    mock_msg = MagicMock()
    mock_msg.message_id = 42

    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=mock_msg)
    bot.edit_message_text = AsyncMock()
    bot.delete_message = AsyncMock()

    async def _run():
        stop = asyncio.Event()

        async def _stop_after(delay):
            await asyncio.sleep(delay)
            stop.set()

        await asyncio.gather(
            _thinking_thread(12345, bot, stop),
            _stop_after(6),  # let 2s grace + one 3s rotation elapse
        )

    asyncio.run(_run())
    bot.send_message.assert_called_once_with(12345, "⚙️ Working...")
    bot.edit_message_text.assert_called()


def test_thinking_thread_deletes_on_completion():
    """After stop_event is set, delete_message is called to clean up."""
    mock_msg = MagicMock()
    mock_msg.message_id = 99

    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=mock_msg)
    bot.edit_message_text = AsyncMock()
    bot.delete_message = AsyncMock()

    async def _run():
        stop = asyncio.Event()

        async def _stop_after(delay):
            await asyncio.sleep(delay)
            stop.set()

        await asyncio.gather(
            _thinking_thread(12345, bot, stop),
            _stop_after(2.5),  # just past grace, before first rotation
        )

    asyncio.run(_run())
    bot.delete_message.assert_called_once_with(12345, 99)


# ── harness ────────────────────────────────────────────────────────────────

TESTS = [
    test_chunk_message_single_chunk_under_limit,
    test_chunk_message_splits_at_newline,
    test_chunk_message_splits_at_limit_when_no_newline,
    test_thinking_thread_skips_on_fast_response,
    test_thinking_thread_sends_and_rotates,
    test_thinking_thread_deletes_on_completion,
]


def run_all() -> tuple[int, int]:
    passed = failed = 0
    for t in TESTS:
        try:
            t()
            print(f"  \u2713 transport: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 transport: {t.__name__}: {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    p, f = run_all()
    print(f"\n{p}/{p+f} passed")
