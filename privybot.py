"""PrivyBot — entry point and startup wiring.

PTB owns the event loop. No threading. No custom async loop.
Initializes the database, builds the app, injects the real Telegram
send into the report layer, then polls.
"""

from dotenv import load_dotenv

load_dotenv()

import os
import asyncio
import logging

# Windows TLS fix: the default ProactorEventLoop intermittently resets async
# TLS handshakes to api.telegram.org (BrokenResourceError). The SelectorEventLoop
# completes handshakes reliably. Standard Windows asyncio workaround — PTB still
# owns the loop; we only choose the loop implementation.
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from db import init_db
from report import init_report
from transport import build_app

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)


async def on_error(update, context) -> None:
    logging.error("Handler error: %s", context.error)

if __name__ == "__main__":
    # Layer 5 — database
    init_db()

    # Build PTB app
    app = build_app()

    # Layer 3 — report (inject real send, Markdown-safe)
    async def send_to_telegram(text: str) -> None:
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        try:
            await app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except Exception:
            await app.bot.send_message(chat_id=chat_id, text=text, parse_mode=None)

    init_report(send_to_telegram)
    app.add_error_handler(on_error)

    # Run
    app.run_polling(drop_pending_updates=True)
