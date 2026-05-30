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

from core.router import route

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Gate — only respond to the allowed chat
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    text = update.message.text or ""
    chat_id = update.effective_chat.id

    # Typing is best-effort; a transient network blip must not block the reply.
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    except Exception:
        pass

    response = await route(chat_id, text)

    # Markdown safety + transient-network resilience: retry the send with a
    # short backoff (the Windows TLS handshake can intermittently reset), and
    # fall back to plain text if Markdown parsing fails.
    for attempt in range(4):
        try:
            await update.message.reply_text(response, parse_mode="Markdown")
            return
        except Exception:
            try:
                await update.message.reply_text(response, parse_mode=None)
                return
            except Exception:
                if attempt == 3:
                    raise
                await asyncio.sleep(1.5)


def build_app():
    app = ApplicationBuilder().token(TOKEN).build()
    # filters.TEXT includes slash commands; router.route() parses them all.
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    return app
