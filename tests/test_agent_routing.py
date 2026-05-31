"""Tests for the intent-routing gate in agent.respond() (ADR-036 Step 4)."""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def _fake_response(content="ok"):
    msg = SimpleNamespace(content=content, tool_calls=[])
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None, model="test")


def test_routing_gate_fires_for_plain_text():
    """model_key=None + Ollama enabled → ai_classify called, focused tools used."""
    from tools.registry import TOOL_REGISTRY

    calendar_tools = ["get_today_schedule", "get_upcoming_events"]

    with (
        patch("bot.agent.ollama_api") as mock_ollama,
        patch("bot.agent.ai_classify", new_callable=AsyncMock) as mock_classify,
        patch("bot.agent._chat", new_callable=AsyncMock) as mock_chat,
        patch("bot.agent.create_thread"),
        patch("bot.agent.add_message"),
        patch("bot.agent.get_context", return_value=[]),
        patch("bot.agent._system_prompt", return_value="sys"),
        patch("bot.agent.update_thread_active"),
        patch("bot.agent.add_message"),
    ):
        mock_ollama.enabled = True
        mock_classify.return_value = ["calendar"]

        with patch("bot.router_ai.ROUTES", {
            "calendar": {"model": "openrouter/free", "tools": calendar_tools},
            "chat": {"model": "ollama/gemma3:4b", "tools": []},
        }), patch("bot.router_ai.VALID_ROUTES", {"calendar", "chat"}):
            mock_chat.return_value = (_fake_response(), "openrouter/free")

            asyncio.run(
                __import__("bot.agent", fromlist=["respond"]).respond(
                    message="what's today?",
                    thread_id="t1",
                    model_key=None,
                )
            )

        mock_classify.assert_called_once()
        chat_call_tools = mock_chat.call_args[0][2]  # third positional arg to _chat
        tool_names = {t["function"]["name"] for t in chat_call_tools if t.get("type") == "function"}
        from tools.registry import ALL_TOOLS
        all_tool_names = {t["function"]["name"] for t in ALL_TOOLS if t.get("type") == "function"}
        assert tool_names != all_tool_names, "Expected focused tools, got ALL_TOOLS"
        assert "get_today_schedule" in tool_names


def test_routing_gate_skips_for_slash_command():
    """model_key='think' → ai_classify NOT called, ALL_TOOLS passed to _chat."""
    with (
        patch("bot.agent.ollama_api") as mock_ollama,
        patch("bot.agent.ai_classify", new_callable=AsyncMock) as mock_classify,
        patch("bot.agent._chat", new_callable=AsyncMock) as mock_chat,
        patch("bot.agent.create_thread"),
        patch("bot.agent.add_message"),
        patch("bot.agent.get_context", return_value=[]),
        patch("bot.agent._system_prompt", return_value="sys"),
        patch("bot.agent.update_thread_active"),
        patch("bot.agent.get_available_model", return_value=None),
    ):
        mock_ollama.enabled = True
        mock_chat.return_value = (_fake_response(), "deepseek/deepseek-chat")

        asyncio.run(
            __import__("bot.agent", fromlist=["respond"]).respond(
                message="plan my week",
                thread_id="t1",
                model_key="think",
            )
        )

        mock_classify.assert_not_called()
        from bot.agent import ALL_TOOLS
        chat_call_tools = mock_chat.call_args[0][2]
        assert chat_call_tools is ALL_TOOLS


# ── harness ────────────────────────────────────────────────────────────────

TESTS = [
    test_routing_gate_fires_for_plain_text,
    test_routing_gate_skips_for_slash_command,
]


def run_all() -> tuple[int, int]:
    passed = failed = 0
    for t in TESTS:
        try:
            t()
            print(f"  \u2713 agent_routing: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 agent_routing: {t.__name__}: {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    p, f = run_all()
    print(f"\n{p}/{p+f} passed")
