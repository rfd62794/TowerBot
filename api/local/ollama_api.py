"""Ollama API client — local model inference with model swap management."""

import os
import subprocess
import requests
import asyncio
import time
import logging
import psutil
import httpx
from infra.db.model_usage import record_model_call

logger = logging.getLogger("privy.ollama")

# VRAM requirements per model in GB
VRAM_REQUIREMENTS_GB = {
    "gemma3:4b":        3.5,
    "qwen2.5:3b":       2.5,
    "qwen2.5:7b":       4.0,
    "qwen2.5-coder:7b": 4.0,
    "llama3.1:8b":      5.0,  # exceeds 4GB — will always skip on RTX 3050 Ti
}

# Read from env so Tower or other hardware can override without code changes
TOTAL_VRAM_GB = float(os.environ.get("OLLAMA_VRAM_GB", "4.0"))


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
        self._starting: bool = False
        self._process = None
    
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
        except Exception as e:
            logger.warning("[Ollama] health_check failed: %s: %s", type(e).__name__, e)
            return False
    
    async def _check_vram(self, model_id: str) -> bool:
        """Check if model fits in available VRAM via /api/ps.
        Falls back to psutil system RAM check if /api/ps fails."""
        required = VRAM_REQUIREMENTS_GB.get(model_id, 3.5)

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.host}/api/ps")
                models = resp.json().get("models", [])
                # Exclude current loaded model — it will be unloaded before swap
                others = [m for m in models if m.get("name") != self._loaded_model]
                used_gb = sum(m.get("size_vram", 0) for m in others) / 1024 ** 3

            available_gb = TOTAL_VRAM_GB - used_gb

            if available_gb < required:
                logger.info(
                    f"[Ollama] Skipping {model_id} — "
                    f"needs {required}GB VRAM, {available_gb:.1f}GB available"
                )
                return False
            return True

        except Exception:
            # /api/ps unavailable — fall back to system RAM check
            available_gb = psutil.virtual_memory().available / 1024 ** 3
            if available_gb < required:
                logger.info(
                    f"[Ollama] Skipping {model_id} — "
                    f"needs {required}GB RAM (fallback check), {available_gb:.1f}GB available"
                )
                return False
            return True

    async def ensure_running(self) -> bool:
        """
        Ensure Ollama service is running. If down, attempt to start it.
        Polls up to 30 seconds for the service to become healthy.
        """
        if self.health_check():
            return True
        if self._starting:
            return False

        self._starting = True
        logger.info("[Ollama] Down — attempting to start...")

        try:
            self._process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (FileNotFoundError, OSError) as e:
            logger.error(f"[Ollama] Cannot start: {e}")
            self._starting = False
            return False

        for i in range(30):
            await asyncio.sleep(1)
            if self.health_check():
                logger.info(f"[Ollama] Ready in {i + 1}s")
                self._starting = False
                return True

        logger.error("[Ollama] Did not come up within 30s — staying on OpenRouter")
        self._starting = False
        return False

    async def warmup(self) -> None:
        """Pre-load model into VRAM to reduce first-request latency."""
        try:
            await self._inference(
                self.model,
                [{"role": "user", "content": "ready"}],
                None,
                0,
            )
            logger.info(f"[Ollama] {self.model} warmed")
        except Exception:
            pass

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
            
            # Check available VRAM before loading (falls back to system RAM)
            if not await self._check_vram(model_name):
                return None  # caller falls through to OpenRouter
            
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
