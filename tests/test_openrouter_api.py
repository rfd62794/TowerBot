"""Tests for api/web/openrouter_api.py — model discovery, validation, chat completion."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


@test("openrouter: get_free_models filters to free tool-capable models only")
def test_get_free_models_filters():
    from unittest.mock import patch, MagicMock
    from api.web.openrouter_api import OpenRouterAPIHandler

    handler = OpenRouterAPIHandler()
    # Reset cache
    OpenRouterAPIHandler._cache = {"models": [], "fetched_at": None}

    mock_data = {
        "data": [
            {
                "id": "free-tool-model",
                "pricing": {"prompt": "0", "completion": "0"},
                "supported_parameters": ["tools", "max_tokens"],
            },
            {
                "id": "paid-tool-model",
                "pricing": {"prompt": "0.001", "completion": "0.002"},
                "supported_parameters": ["tools"],
            },
            {
                "id": "free-no-tools-model",
                "pricing": {"prompt": "0", "completion": "0"},
                "supported_parameters": ["max_tokens"],
            },
        ]
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_data
    mock_resp.raise_for_status = MagicMock()

    with patch("api.web.openrouter_api.requests.get", return_value=mock_resp):
        result = handler.get_free_models()

    assert result == ["free-tool-model"], f"Expected only free+tools model, got {result}"


@test("openrouter: validate_model returns True for known good model")
def test_validate_model_true():
    from unittest.mock import patch
    from api.web.openrouter_api import OpenRouterAPIHandler

    handler = OpenRouterAPIHandler()

    with patch.object(handler, "get_free_models", return_value=["openai/gpt-oss-120b:free", "google/gemma-4-31b-it:free"]):
        assert handler.validate_model("openai/gpt-oss-120b:free") is True


@test("openrouter: validate_model returns False for 404'd model")
def test_validate_model_false():
    from unittest.mock import patch
    from api.web.openrouter_api import OpenRouterAPIHandler

    handler = OpenRouterAPIHandler()

    with patch.object(handler, "get_free_models", return_value=["openai/gpt-oss-120b:free"]):
        assert handler.validate_model("deepseek/deepseek-v4-flash:free") is False


@test("openrouter: chat_completion returns OpenAI-compatible dict")
def test_chat_completion():
    from unittest.mock import patch, MagicMock
    from api.web.openrouter_api import OpenRouterAPIHandler

    handler = OpenRouterAPIHandler()

    mock_response = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    with patch("api.web.openrouter_api.requests.post", return_value=mock_resp):
        result = handler.chat_completion(
            "openai/gpt-oss-120b:free",
            [{"role": "user", "content": "Hello"}],
        )

    assert "choices" in result, f"Expected 'choices' in response, got {result}"
    assert result["choices"][0]["message"]["content"] == "Hello!"


if __name__ == "__main__":
    passed, total = run_all()
    print(f"\n{passed}/{total} passed")
    sys.exit(0 if passed == total else 1)
