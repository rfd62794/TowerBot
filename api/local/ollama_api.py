"""Ollama API client — local model inference."""

import os
import requests
from infra.db.model_usage import record_model_call
import time


class OllamaAPIHandler:
    """Ollama API handler for local model inference."""
    
    def __init__(self):
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
        self.enabled = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
    
    def health_check(self) -> bool:
        """
        Check if Ollama service is running and the configured model is available.
        
        Returns:
            True if reachable and OLLAMA_MODEL is in available models
        """
        if not self.enabled:
            return False
        
        try:
            url = f"{self.host}/api/tags"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # Check if our model is in the available models list
            available_models = [m.get("name") for m in data.get("models", [])]
            return self.model in available_models
        except Exception:
            return False
    
    def chat_completion(self, messages: list, tools: list = None) -> dict:
        """
        Chat completion using Ollama.
        
        Args:
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions
            
        Returns:
            OpenAI-compatible response dict
            
        Raises:
            Exception on connection error
        """
        start_time = time.time()
        
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        
        if tools:
            payload["tools"] = tools
        
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Extract token usage if available
            tokens_in = data.get("prompt_eval_count", 0)
            tokens_out = data.get("eval_count", 0)
            
            # Record successful call
            record_model_call(
                model_id=f"ollama/{self.model}",
                provider="ollama",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=0.0,  # Local models are free
                success=True,
                latency_ms=latency_ms
            )
            
            # Return OpenAI-compatible response
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": data.get("message", {}).get("content", ""),
                        "tool_calls": []
                    }
                }],
                "usage": {
                    "prompt_tokens": tokens_in,
                    "completion_tokens": tokens_out,
                    "total_tokens": tokens_in + tokens_out
                },
                "model": self.model
            }
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Record failed call
            record_model_call(
                model_id=f"ollama/{self.model}",
                provider="ollama",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                success=False,
                error_code=500,  # Connection error
                latency_ms=latency_ms
            )
            
            raise


# Module-level instance
ollama_api = OllamaAPIHandler()
