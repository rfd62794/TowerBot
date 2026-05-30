"""Layer 2 — Agent.

The thinking layer: message in, response string out. Calls OpenRouter,
handles tool calls, injects memory context. Knows nothing about Telegram
or commands. No formatting (that is report.py), no direct SQLite (only db.py).
"""

import os
import json
import logging

from openai import OpenAI

logger = logging.getLogger("privy.agent")

# Track last model used for /status command
_last_model_used: str | None = None


def get_last_model() -> str:
    """Return the last model used, or 'none' if none yet."""
    return _last_model_used or "none"

from core.db import (
    get_context,
    add_message,
    create_thread,
    update_thread_active,
    update_thread_name,
    list_memories,
)
from core.memory import (
    TOOL_DEFINITIONS as MEMORY_TOOL_DEFINITIONS,
    tool_save_memory,
    tool_update_memory,
    tool_retire_memory,
    tool_get_memories,
)
from core.report import report
from core.model_manager import get_available_model, handle_429, handle_success
from tools import TOOL_REGISTRY

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
    + MEMORY_TOOL_DEFINITIONS
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
        "6. Always accept corrections immediately.\n\n"
        "GROUNDING RULES — non-negotiable:\n"
        "Before answering ANY factual question about a specific game, person, place, "
        "company, or current event:\n"
        "1. Call web_search OR wiki_lookup first\n"
        "2. Base your answer on the results returned\n"
        "3. If results are empty — say so honestly\n\n"
        "Never guess factual information. Never fill gaps with plausible content. "
        "The EIC hallucination happened because you guessed. Don't guess. Search."
    )


def _handle_name_thread(thread_id: str, name: str) -> dict:
    update_thread_name(thread_id, name)
    return {"status": "named", "name": name}


def _call(model: str, messages: list, tools):
    kwargs = {"model": model, "messages": messages, "max_tokens": MAX_OUTPUT_TOKENS}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return client.chat.completions.create(**kwargs)


def _extract_retry_after(error) -> float | None:
    """Pull retry_after_seconds from an OpenRouter 429 error body, if present."""
    try:
        body = json.loads(error.response.text)
        return float(body["error"]["metadata"]["retry_after_seconds"])
    except Exception:
        return None


async def _rotate(messages: list, tools):
    """Try dynamically-discovered free models, skipping those in cooldown."""
    global _last_model_used
    while True:
        fallback = get_available_model()
        if fallback is None:
            raise _AllRateLimited()
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
        await report("tool_called", tool_name=name)
        return r
    # Memory tools
    if name == "save_memory":
        r = tool_save_memory(args["key"], args["content"], args["layer"])
        if r is None:
            r = {"error": "save_memory returned None"}
        await report("memory_saved", key=args["key"], layer=args["layer"],
                     content=args["content"])
        return r
    if name == "update_memory":
        r = tool_update_memory(args["key"], args["content"], args.get("reason", ""))
        if r is None:
            r = {"error": "update_memory returned None"}
        await report("memory_updated", key=args["key"], content=args["content"],
                     reason=args.get("reason", ""))
        return r
    if name == "retire_memory":
        r = tool_retire_memory(args["key"], args.get("reason", ""))
        if r is None:
            r = {"error": "retire_memory returned None"}
        await report("memory_retired", key=args["key"], reason=args.get("reason", ""))
        return r
    if name == "get_memories":
        r = tool_get_memories(args["query"])
        if r is None:
            r = {"error": "get_memories returned None", "memories": [], "count": 0}
        keys = [m.get("key") for m in r.get("memories", []) if isinstance(m, dict)]
        await report("memory_retrieved", query=args["query"], count=r.get("count", 0),
                     keys=keys)
        return r
    if name == "name_thread":
        r = _handle_name_thread(thread_id, args["name"])
        if r is None:
            r = {"error": "name_thread returned None"}
        await report("thread_named", name=args["name"])
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
