"""PrivyBot — entry point and startup wiring.

PTB owns the event loop. No threading. No custom async loop.
Initializes the database, builds the app, injects the real Telegram
send into the report layer, then polls.
"""

import os
from dotenv import load_dotenv

# Load .env from absolute path (critical for NSSM service)
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)

import asyncio
import logging
import time

# Windows TLS fix: the default ProactorEventLoop intermittently resets async
# TLS handshakes to api.telegram.org (BrokenResourceError). The SelectorEventLoop
# completes handshakes reliably. Standard Windows asyncio workaround — PTB still
# owns the loop; we only choose the loop implementation.
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from core.db import init_db
from core.report import init_report
from core.transport import handle_message
from core.scheduler import run_scheduler
from telegram.ext import ApplicationBuilder, MessageHandler, filters

# Track startup time for /status command
STARTUP_TIME = time.time()

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/privy.log"),
        logging.StreamHandler(),
    ],
)


async def on_error(update, context) -> None:
    logging.error("Handler error: %s", context.error)


def _validate_startup() -> None:
    """Check required environment variables and database access before starting."""
    errors = []

    if not os.getenv("OPENROUTER_API_KEY"):
        errors.append("OPENROUTER_API_KEY not set in .env")
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        errors.append("TELEGRAM_BOT_TOKEN not set in .env")
    if not os.getenv("TELEGRAM_CHAT_ID"):
        errors.append("TELEGRAM_CHAT_ID not set in .env")

    # Check database accessibility
    try:
        from core.db import DB_PATH
        if not os.path.exists(DB_PATH):
            errors.append(f"Database not found at {DB_PATH}")
    except Exception as e:
        errors.append(f"Database check failed: {e}")

    if errors:
        logging.error("Startup validation failed:")
        for err in errors:
            logging.error(f"  - {err}")
        logging.error("Fix the above issues and restart.")
        exit(1)

    logging.info("Startup validation passed.")


if __name__ == "__main__":
    # Validate before starting
    _validate_startup()

    # Layer 5 — database
    init_db()

    # Build PTB app with post_init hook for scheduler
    async def post_init(application):
        asyncio.create_task(run_scheduler(send_to_telegram))

    app = (ApplicationBuilder()
           .token(os.getenv("TELEGRAM_BOT_TOKEN"))
           .post_init(post_init)
           .build())

    # Add message handler
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

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
