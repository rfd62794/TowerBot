"""Model helpers — utility functions for LLM API calls."""

import httpx
import os
import logging
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


def call_openrouter(model: str, provider: str, prompt: str, **kwargs) -> str:
    """Simple OpenRouter call for autonomous tasks.
    
    Args:
        model: Model ID (e.g., "google/gemini-2.0-flash-001")
        provider: Provider name (e.g., "openrouter")
        prompt: User prompt text
        **kwargs: Additional parameters (currently unused)
    
    Returns:
        Response text from choices[0].message.content
    
    Raises:
        Exception: If API call fails or response is invalid
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable not set")
    
    try:
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60.0
        )
        response.raise_for_status()
        
        data = response.json()
        return data["choices"][0]["message"]["content"]
        
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenRouter HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except (KeyError, IndexError) as e:
        logger.error(f"Invalid OpenRouter response structure: {e}")
        raise
    except Exception as e:
        logger.error(f"OpenRouter call failed: {e}")
        raise


def get_task_model_role(task_type: str) -> str:
    """Get model role for a task type from task_types.yaml.
    
    Args:
        task_type: Task type name (e.g., 'monitor', 'reporter', 'creator', 'planner')
    
    Returns:
        Model role string (e.g., 'fast_intent', 'long_context', 'reasoning')
        Returns 'reasoning' as fallback if task_type not found or error occurs
    """
    try:
        config_path = (Path(__file__).parent.parent /
                       "config" / "task_types.yaml")
        with open(config_path) as f:
            task_types = yaml.safe_load(f)
        return task_types.get(task_type, {}).get("model_role", "reasoning")
    except Exception as e:
        logger.warning(f"Failed to get model_role for {task_type}: {e}, using 'reasoning' fallback")
        return "reasoning"
