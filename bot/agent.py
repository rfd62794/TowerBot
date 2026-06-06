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

# Models permanently removed this session due to 404 (model gone on provider)
_dead_models: set = set()


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
from bot.thinking import set_thinking_tool
from bot.model_manager import get_available_model, handle_429, handle_success, should_skip_model
from tools.registry import TOOL_REGISTRY
from bot.router_ai import (
    classify as ai_classify,
    get_tools_for_routes,
    get_model_for_routes,
)
from api.local.ollama_api import ollama_api

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
        "think() output is visible to you and to Robert — use it honestly.\n\n"
        "TELEGRAM FORMATTING — non-negotiable:\n"
        "Never use markdown tables in responses. Telegram doesn't render them.\n"
        "Format data as labeled lines:\n"
        "  Views: 974\n"
        "  Watch time: 89 min\n"
        "Or as compact inline: \"974 views · 89 min · +1 subscriber\"\n"
        "Use bold labels with HTML: <b>Last 7 days</b>"
    )


def _handle_name_thread(thread_id: str, name: str) -> dict:
    update_thread_name(thread_id, name)
    return {"status": "named", "name": name}


def _wrap_ollama_response(data: dict):
    """Convert Ollama dict response to attribute-accessible object matching OpenAI SDK shape."""
    from types import SimpleNamespace
    msg_data = (data.get("choices") or [{}])[0].get("message") or {}
    tool_calls = []
    for tc in msg_data.get("tool_calls") or []:
        fn = tc.get("function") or {}
        tool_calls.append(SimpleNamespace(
            id=tc.get("id", ""),
            type="function",
            function=SimpleNamespace(
                name=fn.get("name", ""),
                arguments=fn.get("arguments", "{}"),
            ),
        ))
    message = SimpleNamespace(
        role=msg_data.get("role", "assistant"),
        content=msg_data.get("content") or "",
        tool_calls=tool_calls,
    )
    usage_data = data.get("usage") or {}
    usage = SimpleNamespace(
        prompt_tokens=usage_data.get("prompt_tokens", 0),
        completion_tokens=usage_data.get("completion_tokens", 0),
        total_tokens=usage_data.get("total_tokens", 0),
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=usage,
        model=data.get("model", ""),
    )


async def _call(model: str, messages: list, tools):
    from infra.db.model_usage import record_model_call
    import time

    # Route Ollama models to local inference
    if model and model.startswith("ollama/"):
        from api.local.ollama_api import ollama_api
        ollama_model = model.split("/", 1)[1]
        result = await ollama_api.chat(ollama_model, messages, tools)
        if result is not None:
            return _wrap_ollama_response(result)
        # VRAM check failed — fall through to OpenRouter with default
        model = MODELS["default"]

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
        if model and model.startswith("ollama/"):
            provider = "ollama"
        elif model and model.startswith("groq/"):
            provider = "groq"
        elif model and model.startswith("google/"):
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
        if model and model.startswith("ollama/"):
            provider = "ollama"
        elif model and model.startswith("groq/"):
            provider = "groq"
        elif model and model.startswith("google/"):
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
        
        # Skip permanently dead models (404'd this session)
        if fallback in _dead_models:
            handle_429(fallback, 300.0)
            continue
        
        # Check if model should be skipped based on rate limits
        should_skip, skip_reason = should_skip_model(fallback)
        if should_skip:
            await report("model_routed", model=fallback, reason=f"skip: {skip_reason}")
            handle_429(fallback, 60.0)  # Cooldown briefly
            continue
        
        try:
            resp = await _call(fallback, messages, tools)
            handle_success(fallback)
            _last_model_used = fallback
            await report("model_routed", model=fallback, reason="fallback on 429")
            return resp, fallback
        except Exception as e:
            if _is_429(e):
                handle_429(fallback, _extract_retry_after(e) or 60.0)
            elif "404" in str(e):
                # Model gone — validate and permanently remove from session rotation
                try:
                    from api.web.openrouter_api import openrouter_api
                    if not openrouter_api.validate_model(fallback):
                        _dead_models.add(fallback)
                        logger.warning("Removed %s from rotation — 404", fallback)
                except Exception:
                    handle_429(fallback, 300.0)
            else:
                # Other error: cooldown briefly so it is skipped.
                handle_429(fallback, 300.0)
            await report("model_routed", model=fallback, reason=f"skip: {e}")
            continue


async def _chat(model: str, messages: list, tools, allow_rotation: bool = True):
    global _last_model_used
    try:
        resp = await _call(model, messages, tools)
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
    # Update thinking thread with tool name
    set_thinking_tool(name)

    # Tool registry tools first
    if name in TOOL_REGISTRY:
        tool_fn = TOOL_REGISTRY[name]["fn"]

        # Filter to only known parameters from schema (hardening against LLM hallucinations)
        schema_props = (TOOL_REGISTRY[name]["definition"]["function"]
                       .get("parameters", {})
                       .get("properties", {})
                       .keys())
        filtered_args = {k: v for k, v in args.items() if k in schema_props}

        r = tool_fn(**filtered_args)
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
        elif name == "save_memory":
            await report("memory_saved", key=args.get("key", ""),
                         layer=args.get("layer", ""), content=args.get("content", ""))
        elif name == "update_memory":
            await report("memory_updated", key=args.get("key", ""),
                         content=args.get("content", ""), reason=args.get("reason", ""))
        elif name == "retire_memory":
            await report("memory_retired", key=args.get("key", ""),
                         reason=args.get("reason", ""))
        elif name == "get_memories":
            keys = [m.get("key") for m in r.get("memories", []) if isinstance(m, dict)]
            await report("memory_retrieved", query=args.get("query", ""),
                         count=r.get("count", 0), keys=keys)
        else:
            await report("tool_called", tool_name=name)
        
        # Clear tool name from thinking thread
        set_thinking_tool(None)
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


async def respond(message: str, thread_id: str, model_key: str | None = None, max_iter: int | None = None) -> str:
    try:
        # Fallback to env var if max_iter not provided
        if max_iter is None:
            max_iter = int(os.getenv("MAX_ITERATIONS_AUTONOMOUS", "10"))

        # ── Intent routing gate — plain user messages only ─────────────────
        # NOTE: if the previous route was "code" (qwen2.5-coder:7b in VRAM),
        # classify() will request gemma3:4b → Ollama swaps (~10-20s).
        # This is rare and covered by _thinking_thread UX.
        _use_routing = (
            model_key is None
            and not message.lstrip().startswith("[AUTONOMOUS MODE]")
            and ollama_api.enabled
        )
        if _use_routing:
            routes = await ai_classify(message)
            logger.info("[router_ai] routes=%s for: %.80s", routes, message)
            focused_names = get_tools_for_routes(routes)
            model = get_model_for_routes(routes)
            tools = [
                TOOL_REGISTRY[t]["definition"]
                for t in focused_names
                if t in TOOL_REGISTRY
            ] + [NAME_THREAD_TOOL]
            allow_rotation = True
        else:
            # Existing behaviour — full tool set, model from env/command
            tools = ALL_TOOLS
            model = get_available_model() or MODELS.get(model_key) or MODELS["default"]
            allow_rotation = model_key in (None, "default")
        # ──────────────────────────────────────────────────────────────────

        try:
            create_thread(thread_id)
        except Exception:
            pass  # thread already exists

        add_message(thread_id, "user", message)

        messages = [{"role": "system", "content": _system_prompt()}]
        messages.extend(get_context(thread_id, 10))

        iteration = 0
        while iteration < max_iter:
            iteration += 1
            resp, model = await _chat(model, messages, tools, allow_rotation)
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
                # Continue loop for next iteration
                continue
            else:
                logger.info("NO TOOL CALLS in response from [%s]", model)
                break

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
