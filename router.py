"""Layer 1 — Router.

Parses incoming Telegram messages, picks the model key and clean text,
delegates to agent.respond(). Only parses and delegates: no Telegram,
PTB, OpenRouter, or direct SQLite (db.py only).
"""

import uuid

from agent import respond
from db import create_thread, list_memories
from report import report
from model_manager import get_status_report

_current_threads: dict[int, str] = {}


async def _ensure_thread(chat_id: int) -> str:
    if chat_id not in _current_threads:
        thread_id = str(uuid.uuid4())
        create_thread(thread_id)
        _current_threads[chat_id] = thread_id
        await report("thread_new")
    return _current_threads[chat_id]


async def handle_new(chat_id: int) -> None:
    thread_id = str(uuid.uuid4())
    create_thread(thread_id)
    _current_threads[chat_id] = thread_id
    await report("thread_new")


def handle_memories(chat_id: int) -> str:
    memories = list_memories()
    if not memories:
        return "No memories yet."
    by_layer: dict[str, list] = {}
    for m in memories:
        by_layer.setdefault(m["layer"], []).append(m)
    lines = ["🧠 What I know:"]
    for layer in sorted(by_layer):
        lines.append(f"\n[{layer}]")
        for m in by_layer[layer]:
            lines.append(f"• {m['key']}: {m['content']}")
    return "\n".join(lines)


def help_text() -> str:
    return (
        "PrivyBot commands:\n"
        "/think [msg] — DeepSeek (structured)\n"
        "/claude [msg] — Claude Sonnet\n"
        "/new — start fresh thread\n"
        "/memories — list what I know\n"
        "/models — free model availability\n"
        "/help — this message"
    )


async def route(chat_id: int, text: str) -> str:
    if not text or not text.strip():
        return "Say something."

    text = text.strip()

    if text == "/new" or text.startswith("/new"):
        await handle_new(chat_id)
        return "New thread started."
    if text == "/memories" or text.startswith("/memories"):
        return handle_memories(chat_id)
    if text == "/models" or text.startswith("/models"):
        return get_status_report()
    if text == "/help" or text.startswith("/help"):
        return help_text()

    if text.startswith("/think"):
        model_key, message = "think", text[len("/think"):].strip()
    elif text.startswith("/claude"):
        model_key, message = "claude", text[len("/claude"):].strip()
    else:
        model_key, message = "default", text

    if not message:
        return "Say something."

    thread_id = await _ensure_thread(chat_id)
    return await respond(message, thread_id, model_key)
