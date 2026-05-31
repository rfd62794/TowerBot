"""Ollama API client — local model inference with model swap management."""

import os
import requests
import asyncio
import time
import logging
from infra.db.model_usage import record_model_call

logger = logging.getLogger("privy.ollama")


class OllamaSwapManager:
    """
    Singleton manager for Ollama model swapping.
    Serializes all Ollama calls and manages model unloading/loading.
    """
    
    def __init__(self):
        self._loaded_model: str | None = None
        self._lock = asyncio.Lock()
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
        self.enabled = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
    
    def current_model(self) -> str | None:
        """Return the currently loaded model."""
        return self._loaded_model
    
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
    
    async def chat(self, model_id: str, messages: list, tools: list = None) -> dict:
        """
        Chat completion with automatic model swapping.
        
        Args:
            model_id: Model identifier (e.g., "ollama/gemma3:4b" or "gemma3:4b")
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions
            
        Returns:
            OpenAI-compatible response dict
        """
        async with self._lock:
            # Extract model name from model_id if it has prefix
            if model_id.startswith("ollama/"):
                model_name = model_id.replace("ollama/", "")
            else:
                model_name = model_id
            
            # Swap if needed
            swap_start = time.time()
            if self._loaded_model != model_name:
                if self._loaded_model is not None:
                    await self._unload(self._loaded_model)
                    logger.info(f"Unloaded {self._loaded_model} → loading {model_name}")
                self._loaded_model = model_name
            swap_latency_ms = int((time.time() - swap_start) * 1000)
            
            # Inference
            return await self._inference(model_name, messages, tools, swap_latency_ms)
    
    async def _unload(self, model_id: str) -> None:
        """
        Unload a model using keep_alive:0.
        
        Args:
            model_id: Model name to unload
        """
        try:
            url = f"{self.host}/api/generate"
            payload = {
                "model": model_id,
                "keep_alive": 0,
                "prompt": ""
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to unload model {model_id}: {e}")
            # Continue anyway — model may have already been unloaded
    
    async def _inference(self, model_name: str, messages: list, tools: list, swap_latency_ms: int) -> dict:
        """
        Perform actual inference.
        
        Args:
            model_name: Model name for inference
            messages: List of message dicts
            tools: Optional tool definitions
            swap_latency_ms: Time spent swapping models
            
        Returns:
            OpenAI-compatible response dict
        """
        start_time = time.time()
        
        url = f"{self.host}/api/chat"
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
        }
        
        if tools:
            payload["tools"] = tools
        
        try:
            # Run blocking requests in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, requests.post, url, payload, None, 60)
            response.raise_for_status()
            data = response.json()
            
            inference_latency_ms = int((time.time() - start_time) * 1000)
            total_latency_ms = swap_latency_ms + inference_latency_ms
            
            # Extract token usage if available
            tokens_in = data.get("prompt_eval_count", 0)
            tokens_out = data.get("eval_count", 0)
            
            # Record successful call
            record_model_call(
                model_id=f"ollama/{model_name}",
                provider="ollama",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=0.0,  # Local models are free
                success=True,
                latency_ms=total_latency_ms
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
                "model": model_name
            }
        except Exception as e:
            inference_latency_ms = int((time.time() - start_time) * 1000)
            total_latency_ms = swap_latency_ms + inference_latency_ms
            
            # Record failed call
            record_model_call(
                model_id=f"ollama/{model_name}",
                provider="ollama",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                success=False,
                error_code=500,  # Connection error
                latency_ms=total_latency_ms
            )
            
            raise


# Module-level singleton
ollama_swap_manager = OllamaSwapManager()


# Backward compatibility alias
ollama_api = ollama_swap_manager
