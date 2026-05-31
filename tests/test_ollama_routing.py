"""Tests for Ollama routing in _call() — provider dispatch and VRAM fallback."""

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


_OLLAMA_DICT_RESPONSE = {
    "choices": [{"message": {"role": "assistant", "content": "hello from GPU", "tool_calls": []}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    "model": "gemma3:4b",
}


def test_call_routes_ollama_model_to_ollama_api():
    """When model='ollama/gemma3:4b', _call() routes to ollama_api.chat() and returns wrapped response."""
    from bot.agent import _call

    async def _run():
        with patch("api.local.ollama_api.ollama_api") as mock_api:
            mock_api.chat = AsyncMock(return_value=_OLLAMA_DICT_RESPONSE)
            resp = await _call(
                "ollama/gemma3:4b",
                [{"role": "user", "content": "hi"}],
                None,
            )
        return resp, mock_api

    resp, mock_api = asyncio.run(_run())

    mock_api.chat.assert_called_once_with(
        "gemma3:4b",
        [{"role": "user", "content": "hi"}],
        None,
    )
    assert resp.choices[0].message.content == "hello from GPU"
    assert resp.model == "gemma3:4b"
    assert resp.choices[0].message.tool_calls == []


def test_call_falls_through_to_openrouter_when_ollama_returns_none():
    """When ollama_api.chat() returns None (VRAM fail), _call() falls through to OpenRouter client."""
    from bot.agent import _call

    mock_openai_resp = MagicMock()
    mock_openai_resp.choices = [MagicMock()]
    mock_openai_resp.usage = MagicMock()
    mock_openai_resp.usage.prompt_tokens = 0
    mock_openai_resp.usage.completion_tokens = 0

    async def _run():
        with patch("api.local.ollama_api.ollama_api") as mock_api:
            mock_api.chat = AsyncMock(return_value=None)
            with patch("bot.agent.client") as mock_client:
                mock_client.chat.completions.create.return_value = mock_openai_resp
                resp = await _call(
                    "ollama/gemma3:4b",
                    [{"role": "user", "content": "hi"}],
                    None,
                )
        return resp, mock_client

    resp, mock_client = asyncio.run(_run())

    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert not call_kwargs.get("model", "").startswith("ollama/"), (
        "OpenRouter call must not use ollama/ model string"
    )
    assert resp is mock_openai_resp


# ── harness ────────────────────────────────────────────────────────────────

TESTS = [
    test_call_routes_ollama_model_to_ollama_api,
    test_call_falls_through_to_openrouter_when_ollama_returns_none,
]


def run_all() -> tuple[int, int]:
    passed = failed = 0
    for t in TESTS:
        try:
            t()
            print(f"  \u2713 ollama_routing: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 ollama_routing: {t.__name__}: {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    p, f = run_all()
    print(f"\n{p}/{p+f} passed")
