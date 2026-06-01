"""Layer 0 — Transport.

PTB's native async transport. Gates to the allowed chat, shows typing,
delegates to router.route(), and replies. No business logic here.
"""

import os
import asyncio

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

from bot.router import route
from bot.formatter import get_tool_display, format_response

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

THINKING_MESSAGES = [
    "⚙️ Working...",
    "💭 Still thinking...",
    "🔍 Checking sources...",
    "⚙️ Processing...",
    "💭 Almost there...",
    "🔄 Pulling it together...",
]


def set_thinking_tool(tool_name: str | None) -> None:
    """Set the current tool name for thinking thread display."""
    global _current_tool
    _current_tool = tool_name


def _chunk_message(text: str, max_len: int = 4000) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind('\n', 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    return chunks


async def _keep_typing(chat_id: int, bot, stop_event: asyncio.Event) -> None:
    """Re-send typing indicator every 4s until stop_event is set."""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass
        await asyncio.sleep(4)


async def _thinking_thread(chat_id: int, bot, stop_event: asyncio.Event) -> None:
    """Send a rotating status message after a 2s grace period; delete when done."""
    await asyncio.sleep(2)
    if stop_event.is_set():
        return
    try:
        msg = await bot.send_message(chat_id, THINKING_MESSAGES[0])
    except Exception:
        return
    i = 1
    while not stop_event.is_set():
        await asyncio.sleep(3)
        if stop_event.is_set():
            break
        try:
            # Use tool-specific message if set, otherwise rotate generic messages
            if _current_tool:
                icon, name = get_tool_display(_current_tool)
                display_text = f"{icon} {name}..."
            else:
                display_text = THINKING_MESSAGES[i % len(THINKING_MESSAGES)]
                i += 1
            
            await bot.edit_message_text(
                display_text,
                chat_id,
                msg.message_id,
            )
        except Exception:
            pass
    try:
        await bot.delete_message(chat_id, msg.message_id)
    except Exception:
        pass


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Gate — only respond to the allowed chat
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    text = update.message.text or ""
    chat_id = update.effective_chat.id

    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(chat_id, context.bot, stop))
    thinking_task = asyncio.create_task(_thinking_thread(chat_id, context.bot, stop))
    try:
        response = await route(chat_id, text)
    finally:
        stop.set()
        typing_task.cancel()
        thinking_task.cancel()

    # Format response for HTML parse mode
    response = format_response(response)
    
    # Split oversized responses before sending (Telegram hard limit: 4096 chars).
    # Each chunk gets the same HTML → plain-text retry/fallback logic.
    for chunk in _chunk_message(response):
        for attempt in range(4):
            try:
                await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
                break
            except Exception:
                try:
                    await update.message.reply_text(chunk, parse_mode=None)
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    await asyncio.sleep(1.5)


def build_app():
    app = ApplicationBuilder().token(TOKEN).build()
    # filters.TEXT includes slash commands; router.route() parses them all.
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    return app
