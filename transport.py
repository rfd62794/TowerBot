"""Layer 0 — Transport.

Minimal viable Telegram transport using PTB's native async pattern.
No threading wrapper. No custom event loop. PTB owns the loop.
Stable-base scope only: echo "PrivyBot alive" to any text message.
"""

import os

from telegram.ext import ApplicationBuilder, MessageHandler, filters


async def _alive(update, context):
    await update.message.reply_text("PrivyBot alive")


def build_app():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT, _alive))
    return app
