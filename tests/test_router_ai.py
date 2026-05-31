"""Tests for bot/router_ai.py — parse_routes() and get_tools_for_routes().

All tests are sync and require no live Ollama connection (ADR-036 Step 2).
"""

import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import asyncio
from unittest.mock import AsyncMock, patch

from bot.router_ai import parse_routes, get_tools_for_routes, _keyword_fallback


def test_parse_routes_valid_single():
    result = parse_routes('{"routes": ["calendar"]}')
    assert result == ["calendar"]


def test_parse_routes_valid_multi():
    result = parse_routes('{"routes": ["calendar", "email"]}')
    assert result == ["calendar", "email"]


def test_parse_routes_filters_unknown_names():
    result = parse_routes('{"routes": ["calendar", "BOGUS"]}')
    assert result == ["calendar"]


def test_parse_routes_malformed_json_falls_back():
    result = parse_routes("not json at all")
    assert result == ["chat"]


def test_parse_routes_all_unknown_falls_back():
    result = parse_routes('{"routes": ["x", "y"]}')
    assert result == ["chat"]


def test_get_tools_for_routes_merges_and_deduplicates():
    tools = get_tools_for_routes(["calendar", "email"])
    assert "get_today_schedule" in tools
    assert "get_inbox_summary" in tools
    assert len(tools) == len(set(tools)), "Duplicate tools found in merged list"


def test_keyword_fallback_email():
    assert _keyword_fallback("what emails came in?") == ["email"]


def test_keyword_fallback_voidrift():
    assert _keyword_fallback("how's VoidDrift doing?") == ["voidrift"]


def test_keyword_fallback_pure_chat():
    assert _keyword_fallback("hello there") == ["chat"]


def test_classify_escalates_on_chat():
    """Ollama returns 'chat' but message contains 'email' → keyword escalates to email."""
    import bot.router_ai as rai

    async def _run():
        with patch.object(rai.ollama_api, "enabled", True), \
             patch.object(rai.ollama_api, "classify", new_callable=AsyncMock,
                          return_value='{"routes": ["chat"]}'):
            return await rai.classify("what emails came in?")

    result = asyncio.run(_run())
    assert result == ["email"]


# ── harness ────────────────────────────────────────────────────────────────

TESTS = [
    test_parse_routes_valid_single,
    test_parse_routes_valid_multi,
    test_parse_routes_filters_unknown_names,
    test_parse_routes_malformed_json_falls_back,
    test_parse_routes_all_unknown_falls_back,
    test_get_tools_for_routes_merges_and_deduplicates,
    test_keyword_fallback_email,
    test_keyword_fallback_voidrift,
    test_keyword_fallback_pure_chat,
    test_classify_escalates_on_chat,
]


def run_all() -> tuple[int, int]:
    passed = failed = 0
    for t in TESTS:
        try:
            t()
            print(f"  \u2713 router_ai: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 router_ai: {t.__name__}: {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    p, f = run_all()
    print(f"\n{p}/{p+f} passed")
