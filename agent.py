"""Layer 2 — Agent.

The thinking layer: message in, response string out. Calls OpenRouter,
handles tool calls, injects memory context. Knows nothing about Telegram
or commands. No formatting (that is report.py), no direct SQLite (only db.py).
"""

import os
import json

from openai import OpenAI

from db import (
    get_context,
    add_message,
    create_thread,
    update_thread_active,
    update_thread_name,
    list_memories,
)
from memory import (
    TOOL_DEFINITIONS,
    tool_save_memory,
    tool_update_memory,
    tool_retire_memory,
    tool_get_memories,
)
from report import report

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
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

ALL_TOOLS = TOOL_DEFINITIONS + [NAME_THREAD_TOOL]


FREE_MODEL_FALLBACKS = [
    "deepseek/deepseek-v4-flash:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "nousresearch/hermes-3-405b-instruct:free",
    "google/gemma-4-31b:free",
    "moonshotai/kimi-k2.6:free",
]


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
        "6. Always accept corrections immediately."
    )


def _handle_name_thread(thread_id: str, name: str) -> dict:
    update_thread_name(thread_id, name)
    return {"status": "named", "name": name}


def _call(model: str, messages: list, tools):
    kwargs = {"model": model, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return client.chat.completions.create(**kwargs)


async def _rotate_fallbacks(messages: list, tools, failed_model: str):
    for m in FREE_MODEL_FALLBACKS:
        if m == failed_model:
            continue
        try:
            resp = _call(m, messages, tools)
            await report("model_routed", model=m, reason="fallback on 429")
            return resp, m
        except Exception as e:
            # Skip any unavailable model (throttled, invalid id, etc.).
            await report("model_routed", model=m, reason=f"skip: {e}")
            continue
    raise _AllRateLimited()


async def _chat(model: str, messages: list, tools):
    try:
        return _call(model, messages, tools), model
    except Exception as e:
        if _is_429(e):
            return await _rotate_fallbacks(messages, tools, failed_model=model)
        if not _is_402(e):
            raise
        if model == MODELS["default"]:
            raise _CreditsExhausted()
        await report("error", message="Credit limit hit, fell back to free model")
        try:
            return _call(MODELS["default"], messages, tools), MODELS["default"]
        except Exception as e2:
            if _is_402(e2):
                raise _CreditsExhausted()
            raise


async def _execute(thread_id: str, name: str, args: dict) -> dict:
    if name == "save_memory":
        r = tool_save_memory(args["key"], args["content"], args["layer"])
        await report("memory_saved", key=args["key"], layer=args["layer"],
                     content=args["content"])
        return r
    if name == "update_memory":
        r = tool_update_memory(args["key"], args["content"], args.get("reason", ""))
        await report("memory_updated", key=args["key"], content=args["content"],
                     reason=args.get("reason", ""))
        return r
    if name == "retire_memory":
        r = tool_retire_memory(args["key"], args.get("reason", ""))
        await report("memory_retired", key=args["key"], reason=args.get("reason", ""))
        return r
    if name == "get_memories":
        r = tool_get_memories(args["query"])
        keys = [m["key"] for m in r.get("memories", [])]
        await report("memory_retrieved", query=args["query"], count=r.get("count", 0),
                     keys=keys)
        return r
    if name == "name_thread":
        r = _handle_name_thread(thread_id, args["name"])
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

        model = MODELS.get(model_key) or MODELS["default"]
        resp, model = await _chat(model, messages, ALL_TOOLS)
        msg = resp.choices[0].message

        if msg.tool_calls:
            messages.append(_assistant_tool_msg(msg))
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = await _execute(thread_id, tc.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })
            resp, model = await _chat(model, messages, None)
            msg = resp.choices[0].message

        text = msg.content or ""
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
