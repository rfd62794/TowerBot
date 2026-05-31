"""Layer 2 — Agent.

The thinking layer: message in, response string out. Calls OpenRouter,
handles tool calls, injects memory context. Knows nothing about Telegram
or commands. No formatting (that is report.py), no direct SQLite (only db.py).
"""

import os
import json
import logging
import time

from openai import OpenAI

logger = logging.getLogger("privy.agent")

# Track last model used for /status command
_last_model_used: str | None = None


def get_last_model() -> str:
    """Return the last model used, or 'none' if none yet."""
    return _last_model_used or "none"

from infra.db import (
    get_context,
    add_message,
    create_thread,
    update_thread_active,
    update_thread_name,
    list_memories,
)
from bot.memory import (
    tool_save_memory,
    tool_update_memory,
    tool_retire_memory,
    tool_get_memories,
)
from bot.report import report
from bot.model_manager import get_available_model, handle_429, handle_success, should_skip_model
from tools.registry import TOOL_REGISTRY

# max_retries=0: we manage 429 rotation ourselves; the SDK's internal retries
# add 19-23s blocking waits before our fallback logic can run.
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    max_retries=0,
)

MODELS = {
    "default": os.getenv("DEFAULT_MODEL"),
    "think": os.getenv("DEEP_MODEL"),
    "claude": os.getenv("CLAUDE_MODEL"),
}

NAME_THREAD_TOOL = {
    "type": "function",
    "function": {
        "name": "name_thread",
        "description": "Name the current thread based on the opening message. "
                       "Call after your FIRST response only. 3-5 words. "
                       "Specific. Never generic.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Thread name, 3-5 words"},
            },
            "required": ["name"],
        },
    },
}

ALL_TOOLS = (
    [TOOL_REGISTRY[t]["definition"] for t in TOOL_REGISTRY]
    + [NAME_THREAD_TOOL]
)


# Cap output tokens: some providers (e.g. Venice for Llama) reject the model's
# large default max_completion_tokens. 8000 is well under provider caps.
MAX_OUTPUT_TOKENS = 8000


class _CreditsExhausted(Exception):
    pass


class _AllRateLimited(Exception):
    pass


def _is_402(e: Exception) -> bool:
    return "402" in str(e) or "Insufficient credits" in str(e)


def _is_429(e: Exception) -> bool:
    return "429" in str(e) or "rate-limited" in str(e) or "Rate limit" in str(e)


def _system_prompt() -> str:
    memories = list_memories()
    if memories:
        mem_text = "\n".join(
            f"- [{m['layer']}] {m['key']}: {m['content']}" for m in memories
        )
    else:
        mem_text = "(nothing yet)"
    return (
        "You are PrivyBot, Robert Floyd Dugger's personal AI assistant.\n\n"
        "What you know about Robert:\n"
        f"{mem_text}\n\n"
        "Memory rules — non-negotiable:\n"
        "1. Call name_thread after first response in every new thread. 3-5 words. Specific.\n"
        "2. Call save_memory when you learn something worth keeping. Announce it.\n"
        "3. Call update_memory when info changes.\n"
        "4. Call get_memories at start of new topic.\n"
        "5. Never save casual conversation. Save: projects, decisions, preferences, "
        "goals, people, technical choices.\n"
        "6. Always accept corrections immediately.\n"
        "7. When Robert says he WILL do something with a time reference — call "
        "save_commitment, not save_memory.\n\n"
        "COMMITMENT DETECTION — non-negotiable:\n"
        "These phrases always trigger save_commitment:\n"
        "  'I'm going to X'\n"
        "  'I'll do X this weekend'\n"
        "  'I need to do X by Y'\n"
        "  'planning to X after Z'\n"
        "  'going to record X'\n"
        "  'will finish X by Y'\n"
        "  'I want to X before Y'\n"
        "Do not use save_memory for these. "
        "Do not use add_task unless already in the weekly plan. "
        "Use save_commitment. Always.\n\n"
        "GROUNDING RULES — non-negotiable:\n"
        "Before answering ANY factual question about a specific game, person, place, "
        "company, or current event:\n"
        "1. Call web_search OR wiki_lookup first\n"
        "2. Base your answer on the results returned\n"
        "3. If results are empty — say so honestly\n\n"
        "Never guess factual information. Never fill gaps with plausible content. "
        "The EIC hallucination happened because you guessed. Don't guess. Search.\n\n"
        "THINK BEFORE COMPLEX ACTIONS:\n"
        "For questions requiring multiple tool calls or multi-step reasoning:\n"
        "  1. Call think() with your plan first\n"
        "  2. Execute the plan step by step\n"
        "  3. Call think() again if direction changes\n\n"
        "For simple single-tool questions:\n"
        "  Skip think() — answer directly.\n\n"
        "think() output is visible to you and to Robert — use it honestly."
    )


def _handle_name_thread(thread_id: str, name: str) -> dict:
    update_thread_name(thread_id, name)
    return {"status": "named", "name": name}


def _call(model: str, messages: list, tools):
    from infra.db.model_usage import record_model_call
    import time
    
    start_time = time.time()
    kwargs = {"model": model, "messages": messages, "max_tokens": MAX_OUTPUT_TOKENS}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    
    try:
        resp = client.chat.completions.create(**kwargs)
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Extract token usage if available
        tokens_in = resp.usage.prompt_tokens if resp.usage else 0
        tokens_out = resp.usage.completion_tokens if resp.usage else 0
        
        # Determine provider from model ID
        if model.startswith("ollama/"):
            provider = "ollama"
        elif model.startswith("groq/"):
            provider = "groq"
        elif model.startswith("google/"):
            provider = "google"
        else:
            provider = "openrouter"
        
        # Record successful call
        record_model_call(
            model_id=model,
            provider=provider,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=0.0,  # Free models for now
            success=True,
            latency_ms=latency_ms
        )
        
        return resp
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Determine provider
        if model.startswith("ollama/"):
            provider = "ollama"
        elif model.startswith("groq/"):
            provider = "groq"
        elif model.startswith("google/"):
            provider = "google"
        else:
            provider = "openrouter"
        
        # Extract error code
        error_code = None
        if "429" in str(e):
            error_code = 429
        elif "404" in str(e):
            error_code = 404
        elif "403" in str(e):
            error_code = 403
        
        # Record failed call
        record_model_call(
            model_id=model,
            provider=provider,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            success=False,
            error_code=error_code,
            latency_ms=latency_ms
        )
        
        raise


def _extract_retry_after(error) -> float | None:
    """Pull retry_after_seconds from an OpenRouter 429 error body, if present."""
    try:
        body = json.loads(error.response.text)
        return float(body["error"]["metadata"]["retry_after_seconds"])
    except Exception:
        return None


async def _rotate(messages: list, tools):
    """Try dynamically-discovered free models, skipping those in cooldown or rate-limited."""
    global _last_model_used
    while True:
        fallback = get_available_model()
        if fallback is None:
            raise _AllRateLimited()
        
        # Check if model should be skipped based on rate limits
        should_skip, skip_reason = should_skip_model(fallback)
        if should_skip:
            await report("model_routed", model=fallback, reason=f"skip: {skip_reason}")
            handle_429(fallback, 60.0)  # Cooldown briefly
            continue
        
        try:
            resp = _call(fallback, messages, tools)
            handle_success(fallback)
            _last_model_used = fallback
            await report("model_routed", model=fallback, reason="fallback on 429")
            return resp, fallback
        except Exception as e:
            if _is_429(e):
                handle_429(fallback, _extract_retry_after(e) or 60.0)
            else:
                # Invalid id or other error: cooldown briefly so it is skipped.
                handle_429(fallback, 300.0)
            await report("model_routed", model=fallback, reason=f"skip: {e}")
            continue


async def _chat(model: str, messages: list, tools, allow_rotation: bool = True):
    global _last_model_used
    try:
        resp = _call(model, messages, tools)
        handle_success(model)
        _last_model_used = model
        return resp, model
    except Exception as e:
        if _is_429(e):
            if not allow_rotation:
                raise
            handle_429(model, _extract_retry_after(e) or 60.0)
            return await _rotate(messages, tools)
        if not _is_402(e):
            raise
        if model == MODELS["default"]:
            raise _CreditsExhausted()
        await report("error", message="Credit limit hit, fell back to free model")
        return await _chat(MODELS["default"], messages, tools, allow_rotation=True)


async def _execute(thread_id: str, name: str, args: dict) -> dict:
    # Tool registry tools first
    if name in TOOL_REGISTRY:
        tool_fn = TOOL_REGISTRY[name]["fn"]
        r = tool_fn(**args)
        if r is None:
            r = {"error": f"Tool {name} returned None"}
        elif not isinstance(r, dict):
            r = {"error": f"Tool {name} returned unexpected type: {type(r)}"}
        if name == "save_commitment":
            await report("commitment_saved",
                         description=args.get("description", ""),
                         deadline=args.get("deadline"))
        elif name == "think":
            await report("thought", thought=args.get("thought", ""))
        else:
            await report("tool_called", tool_name=name)
        return r
    # Memory tools
    if name == "save_memory":
        key = args.get("key", "")
        content = args.get("content", "")
        layer = args.get("layer", "facts")
        if not key or not content:
            return {"error": "save_memory called without required key/content"}
        r = tool_save_memory(key, content, layer)
        if r is None:
            r = {"error": "save_memory returned None"}
        await report("memory_saved", key=key, layer=layer, content=content)
        return r
    if name == "update_memory":
        key = args.get("key", "")
        content = args.get("content", "")
        if not key or not content:
            return {"error": "update_memory called without required key/content"}
        r = tool_update_memory(key, content, args.get("reason", ""))
        if r is None:
            r = {"error": "update_memory returned None"}
        await report("memory_updated", key=key, content=content,
                     reason=args.get("reason", ""))
        return r
    if name == "retire_memory":
        key = args.get("key", "")
        if not key:
            return {"error": "retire_memory called without required key"}
        r = tool_retire_memory(key, args.get("reason", ""))
        if r is None:
            r = {"error": "retire_memory returned None"}
        await report("memory_retired", key=key, reason=args.get("reason", ""))
        return r
    if name == "get_memories":
        query = args.get("query", "")
        if not query:
            return {"error": "get_memories called without required query"}
        r = tool_get_memories(query)
        if r is None:
            r = {"error": "get_memories returned None", "memories": [], "count": 0}
        keys = [m.get("key") for m in r.get("memories", []) if isinstance(m, dict)]
        await report("memory_retrieved", query=query, count=r.get("count", 0),
                     keys=keys)
        return r
    if name == "name_thread":
        thread_name = args.get("name", "")
        if not thread_name:
            return {"error": "name_thread called without required name"}
        r = _handle_name_thread(thread_id, thread_name)
        if r is None:
            r = {"error": "name_thread returned None"}
        await report("thread_named", name=thread_name)
        return r
    return {"status": "error", "reason": f"unknown tool {name}"}


def _assistant_tool_msg(msg):
    return {
        "role": "assistant",
        "content": msg.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ],
    }


async def respond(message: str, thread_id: str, model_key: str = "default") -> str:
    try:
        try:
            create_thread(thread_id)
        except Exception:
            pass  # thread already exists

        add_message(thread_id, "user", message)

        messages = [{"role": "system", "content": _system_prompt()}]
        messages.extend(get_context(thread_id, 10))

        allow_rotation = (model_key == "default")
        model = MODELS.get(model_key) or MODELS["default"]
        resp, model = await _chat(model, messages, ALL_TOOLS, allow_rotation)
        msg = resp.choices[0].message

        if msg.tool_calls:
            messages.append(_assistant_tool_msg(msg))
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                logger.info("TOOL CALL [%s]: %s %s", model, tc.function.name, args)
                result = await _execute(thread_id, tc.function.name, args)
                logger.info("TOOL RESULT: %s", result)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })
            resp, model = await _chat(model, messages, None, allow_rotation)
            msg = resp.choices[0].message
        else:
            logger.info("NO TOOL CALLS in response from [%s]", model)

        text = msg.content or ""
        if any(tok in text for tok in ("<tool_call>", "<arg_key>", "<function", "```tool")):
            logger.warning(
                "RAW TOOL-CALL TEXT leaked from [%s] (model faked tools): %.200s",
                model, text,
            )
        add_message(thread_id, "assistant", text)
        update_thread_active(thread_id)
        return text

    except _CreditsExhausted:
        return "OpenRouter credits exhausted. Check your account."
    except _AllRateLimited:
        return (
            "All free models rate-limited. Try /think or /claude, "
            "or wait 60 seconds."
        )
    except Exception as e:
        await report("error", message=str(e))
        return "Something went wrong. Try again."
