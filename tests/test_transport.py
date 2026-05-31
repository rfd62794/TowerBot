"""Tests for transport-layer helpers — message chunking."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from bot.transport import _chunk_message


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


# ── harness ────────────────────────────────────────────────────────────────

TESTS = [
    test_chunk_message_single_chunk_under_limit,
    test_chunk_message_splits_at_newline,
    test_chunk_message_splits_at_limit_when_no_newline,
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
