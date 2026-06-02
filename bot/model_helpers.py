"""Model helpers — utility functions for LLM API calls."""

import httpx
import os
import logging

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
