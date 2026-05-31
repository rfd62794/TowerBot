"""OpenRouter API handler — model discovery, validation, and chat completions."""

import os
import logging
import requests
from datetime import datetime

logger = logging.getLogger("privy.openrouter")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterAPIHandler:
    """Dedicated handler for OpenRouter API interactions."""

    _cache: dict = {"models": [], "fetched_at": None}

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://rfditservices.com",
            "X-Title": "PrivyBot",
        }

    def get_free_models(self) -> list[str]:
        """
        Fetch free, tool-capable models from OpenRouter. Cached 1h in memory.

        Returns:
            List of model IDs with free pricing and tool-calling support
        """
        now = datetime.utcnow()
        fetched_at = OpenRouterAPIHandler._cache["fetched_at"]

        if fetched_at is None or (now - fetched_at).seconds > 3600:
            try:
                resp = requests.get(
                    f"{OPENROUTER_BASE_URL}/models",
                    headers=self.headers,
                    params={"supported_parameters": "tools"},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json().get("data", [])

                models = []
                for model in data:
                    pricing = model.get("pricing", {})
                    is_free = (
                        pricing.get("prompt") == "0"
                        and pricing.get("completion") == "0"
                    )
                    has_tools = "tools" in model.get("supported_parameters", [])
                    if is_free and has_tools:
                        models.append(model["id"])

                OpenRouterAPIHandler._cache["models"] = models
                OpenRouterAPIHandler._cache["fetched_at"] = now
                logger.info("OpenRouter: discovered %d free tool-capable models", len(models))
            except Exception as e:
                logger.error("OpenRouter get_free_models failed: %s", e)

        return OpenRouterAPIHandler._cache["models"]

    def validate_model(self, model_id: str) -> bool:
        """
        Check if a model ID is currently available on OpenRouter.

        Args:
            model_id: OpenRouter model identifier

        Returns:
            True if model is in the current free model list
        """
        return model_id in self.get_free_models()

    def chat_completion(
        self, model_id: str, messages: list, tools: list = None
    ) -> dict:
        """
        Send a chat completion request to OpenRouter.

        Args:
            model_id: Model to use
            messages: OpenAI-format message list
            tools: Optional tool definitions

        Returns:
            OpenAI-compatible response dict

        Raises:
            requests.HTTPError: On 404 (model gone) or other HTTP errors
        """
        payload = {
            "model": model_id,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools

        resp = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=self.headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()


openrouter_api = OpenRouterAPIHandler()
