"""Model helpers — utility functions for LLM API calls."""

import httpx
import os
import logging

logger = logging.getLogger(__name__)


def call_groq(model: str, provider: str, prompt: str, **kwargs) -> str:
    """Direct Groq API call for fast_intent role.
    
    Args:
        model: Model ID (e.g., "llama-3.1-70b-versatile")
        provider: Provider name (e.g., "groq")
        prompt: User prompt text
        **kwargs: Additional parameters (currently unused)
    
    Returns:
        Response text from choices[0].message.content
    
    Raises:
        Exception: If API call fails or response is invalid
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable not set")
    
    try:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30.0
        )
        response.raise_for_status()
        
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError(f"Groq returned empty choices: {data}")
        return choices[0]["message"]["content"]
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Groq HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Invalid Groq response structure: {e}")
        raise
    except Exception as e:
        logger.error(f"Groq call failed: {e}")
        raise


def call_gemini(model: str, provider: str, prompt: str, **kwargs) -> str:
    """Direct Google Gemini API call for long_context and chat roles.
    
    Args:
        model: Model ID (e.g., "gemini-2.0-flash")
        provider: Provider name (e.g., "google")
        prompt: User prompt text
        **kwargs: Additional parameters (currently unused)
    
    Returns:
        Response text from candidates[0].content.parts[0].text
    
    Raises:
        Exception: If API call fails or response is invalid
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    try:
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
            },
            timeout=60.0
        )
        response.raise_for_status()
        
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError(f"Gemini returned empty candidates: {data}")
        return candidates[0]["content"]["parts"][0]["text"]
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Gemini HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Invalid Gemini response structure: {e}")
        raise
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        raise


def call_openrouter(model: str, provider: str, prompt: str, **kwargs) -> str:
    """OpenRouter API call for models not available via direct providers.
    
    Args:
        model: Model ID (e.g., "deepseek/deepseek-chat")
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
        choices = data.get("choices") or []
        if not choices:
            raise ValueError(f"OpenRouter returned empty choices: {data}")
        return choices[0]["message"]["content"]
        
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenRouter HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Invalid OpenRouter response structure: {e}")
        raise
    except Exception as e:
        logger.error(f"OpenRouter call failed: {e}")
        raise


def get_call_fn(provider: str):
    """Return the appropriate call function for a given provider.
    
    Args:
        provider: Provider name (e.g., "groq", "google", "openrouter")
    
    Returns:
        Callable function that takes (model, provider, prompt, **kwargs) and returns str
    """
    if provider == "groq":
        return call_groq
    elif provider == "google":
        return call_gemini
    else:
        return call_openrouter  # fallback for openrouter, ollama, etc.
