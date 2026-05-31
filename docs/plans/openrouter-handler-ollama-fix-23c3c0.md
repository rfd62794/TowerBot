# OpenRouter Handler + Ollama Routing Fix

Dedicate a new `api/web/openrouter_api.py` for model discovery/validation, remove stale hardcoded models, add 404-based permanent session removal, and fix the silent Ollama routing failure.

## Context

- `OLLAMA_ENABLED=true` is set — Ollama is skipped for a code reason, not env
- `fetch_free_tool_models()` already does model discovery in `model_manager.py` (24h cache)
- `_rotate()` in `agent.py` puts 404'd models in 300s cooldown — they re-enter rotation
- `deepseek/deepseek-v4-flash:free` is hardcoded in `SEED_FREE_MODELS` but returns 404

---

## Files Touched

- `api/web/openrouter_api.py` — new
- `bot/model_manager.py` — update SEED_FREE_MODELS, wire new handler, add Ollama log
- `tests/test_openrouter_api.py` — new, 4 tests

---

## Step 1 — `api/web/openrouter_api.py`

```python
class OpenRouterAPIHandler:
    __init__: api_key, headers (Authorization + HTTP-Referer + X-Title)

    get_free_models() -> list[str]:
        GET /api/v1/models?supported_parameters=tools
        Filter: pricing.prompt == "0" AND pricing.completion == "0"
        In-memory 1h cache (class-level dict, not BaseAPIHandler):
          _cache = {"models": [], "fetched_at": None}
          if fetched_at is None or (now - fetched_at).seconds > 3600: refetch
        Returns list of model IDs

    validate_model(model_id) -> bool:
        Return model_id in self.get_free_models()

    chat_completion(model_id, messages, tools=None) -> dict:
        POST /api/v1/chat/completions
        Raises on 404 so caller can remove from rotation
```

Note: `chat_completion` is a thin wrapper — `agent.py`'s `_call` stays as the main path, but `_rotate` can use `validate_model` before retrying a 404'd model.

---

## Step 2 — `bot/model_manager.py`

**SEED_FREE_MODELS:** Remove `deepseek/deepseek-v4-flash:free`. List becomes fallback-only; live discovery is primary.

**`fetch_free_tool_models()`:** Wire to `OpenRouterAPIHandler.get_free_models()` instead of inline httpx call.

**`get_available_model()`:** Add explicit log line before the Ollama check:
```python
logger.info("Checking Ollama: enabled=%s health=%s", ollama_api.enabled, ollama_api.health_check())
```
This shows exactly why Ollama is skipped in every run.

**Permanent 404 removal:** Add a module-level `_dead_models: set = set()`. In `_rotate()` in `agent.py`, when a non-429 error (i.e. 404) fires, call `validate_model()`. If it returns False, add to `_dead_models` and log `"Removed {model} from rotation — 404"`. Skip `_dead_models` in `get_available_model()`.

---

## Step 3 — `tests/test_openrouter_api.py` (4 tests)

1. `get_free_models filters correctly` — mock response with mixed pricing, assert only free+tools models returned
2. `validate_model returns True for known good model` — mock get_free_models
3. `validate_model returns False for removed model` — deepseek not in mock list
4. `chat_completion returns OpenAI-compatible dict` — mock POST

---

## Test count: 284 + 4 = 288

---

## Questions / Stop Rule

- Only `api/web/openrouter_api.py`, `bot/model_manager.py`, `bot/agent.py` (dead_models), `tests/test_openrouter_api.py`
- The Ollama log will reveal root cause on next run — do not guess further
- `deepseek/deepseek-v4-flash:free` removed from SEED_FREE_MODELS permanently
