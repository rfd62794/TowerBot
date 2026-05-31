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

from infra.db import init_db
from bot.report import init_report
from bot.transport import handle_message
from bot.scheduler import run_scheduler, check_missed_briefing
from bot.autonomous import setup_autonomous_scheduler
from infra.polling import polling_manager
from telegram.ext import ApplicationBuilder, MessageHandler, filters
from telegram.request import HTTPXRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
        from infra.db import DB_PATH
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


def start_with_retry(application, max_attempts: int = 5, delay: int = 3):
    """
    Retry bot startup on TLS errors.
    These are transient Windows networking issues that resolve on retry.
    Creates a fresh event loop before each attempt since PTB closes it on failure.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            # Create fresh event loop for each attempt
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            logging.info(f"Starting bot (attempt {attempt}/{max_attempts})")
            application.run_polling(drop_pending_updates=True)
            break  # clean exit
        except Exception as e:
            err = str(e).lower()
            is_tls = any(word in err for word in [
                "connecterror", "tls", "ssl", "handshake", "connect"
            ])
            if is_tls and attempt < max_attempts:
                logging.warning(f"TLS error on attempt {attempt}. Retrying in {delay}s: {e}")
                time.sleep(delay)
                delay *= 2  # exponential backoff
            else:
                logging.error(f"Fatal error after {attempt} attempts: {e}")
                raise


if __name__ == "__main__":
    # Validate before starting
    _validate_startup()

    # Layer 5 — database
    init_db()

    async def _start_polling():
        """
        Start PollingManager with graceful fallback.
        If it fails — heartbeat continues as before.
        """
        await asyncio.sleep(5)
        try:
            polling_manager.register_defaults()
            asyncio.create_task(polling_manager.run_loop())
            logging.info("[startup] PollingManager started")
        except Exception as e:
            logging.warning(f"[startup] PollingManager failed: {e} — using heartbeat polling only")

    # Build PTB app with post_init hook for scheduler
    async def post_init(application):
        asyncio.create_task(run_scheduler(send_to_telegram))
        asyncio.create_task(check_missed_briefing(send_to_telegram))
        asyncio.create_task(_start_polling())

        from api.local.ollama_api import ollama_api
        if ollama_api.enabled:
            async def _start_ollama():
                if await ollama_api.ensure_running():
                    await ollama_api.warmup()
            asyncio.create_task(_start_ollama())

        # Start APScheduler for autonomous tasks
        ap_scheduler = AsyncIOScheduler(timezone="America/New_York")
        setup_autonomous_scheduler(ap_scheduler, send_to_telegram)
        ap_scheduler.start()
        logging.info("[startup] APScheduler started with autonomous tasks")

        # Store scheduler for cleanup
        application._ap_scheduler = ap_scheduler

    # HTTPXRequest with extended timeouts for Windows TLS handshake reliability
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=30,
        write_timeout=30,
        connect_timeout=30,
        pool_timeout=30,
    )

    app = (ApplicationBuilder()
           .token(os.getenv("TELEGRAM_BOT_TOKEN"))
           .request(request)
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

    # Run with retry wrapper for TLS errors
    start_with_retry(app)
