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

from bot.router import route

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))


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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Gate — only respond to the allowed chat
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    text = update.message.text or ""
    chat_id = update.effective_chat.id

    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(chat_id, context.bot, stop))
    try:
        response = await route(chat_id, text)
    finally:
        stop.set()
        typing_task.cancel()

    # Split oversized responses before sending (Telegram hard limit: 4096 chars).
    # Each chunk gets the same Markdown → plain-text retry/fallback logic.
    for chunk in _chunk_message(response):
        for attempt in range(4):
            try:
                await update.message.reply_text(chunk, parse_mode="Markdown")
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
