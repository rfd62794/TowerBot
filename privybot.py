"""PrivyBot — entry point only.

PTB owns the event loop. No threading. No custom async loop.
"""

from dotenv import load_dotenv

load_dotenv()

from transport import build_app

if __name__ == "__main__":
    app = build_app()
    app.run_polling()
