"""Ollama API client — local model inference."""

import os
import requests
from api._handler import BaseAPIHandler


class OllamaAPIHandler(BaseAPIHandler):
    CACHE_PREFIX = "ollama"
    BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    def _get_client(self):
        return None  # HTTP only
    
    def chat(self, model: str, messages: list, tools: list = None, **kwargs) -> dict:
        """
        Chat completion using Ollama.
        
        Args:
            model: Model name (e.g., "gemma3:4b")
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions
            **kwargs: Additional parameters (temperature, etc.)
            
        Returns:
            Dict with response content and metadata
        """
        params_hash = self.hash(model, str(messages), str(tools), str(kwargs))
        
        def _live() -> dict:
            url = f"{self.BASE_URL}/api/chat"
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                **kwargs
            }
            
            if tools:
                payload["tools"] = tools
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            return {
                "content": data.get("message", {}).get("content", ""),
                "model": data.get("model"),
                "done": data.get("done", True),
                "total_duration_ms": data.get("total_duration", 0) / 1_000_000,
                "load_duration_ms": data.get("load_duration", 0) / 1_000_000,
                "prompt_eval_count": data.get("prompt_eval_count", 0),
                "eval_count": data.get("eval_count", 0),
            }
        
        return self.call("chat", params_hash, _live, stale_ok=False)
    
    def list_models(self) -> dict:
        """List available local models."""
        def _live() -> dict:
            url = f"{self.BASE_URL}/api/tags"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model in data.get("models", []):
                models.append({
                    "name": model.get("name"),
                    "size": model.get("size", 0),
                    "modified_at": model.get("modified_at"),
                })
            
            return {"models": models}
        
        return self.call("list", "all", _live, stale_ok=True, ttl_hours=24)
    
    def pull_model(self, model: str) -> dict:
        """Pull a model from Ollama registry."""
        def _live() -> dict:
            url = f"{self.BASE_URL}/api/pull"
            payload = {"name": model, "stream": False}
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            return {"status": "pulled", "model": model}
        
        return self.call("pull", model, _live, stale_ok=False)


# Module-level instance
ollama_api = OllamaAPIHandler()
