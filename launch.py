"""Launch wrapper for PrivyBot with crash-revert watchdog.

Starts privybot.py as subprocess, watches for crashes.
If a deploy causes a crash within 60 seconds, auto-revert to last good commit.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path
_root = Path(__file__).parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DEPLOY_RESTART_FLAG = _root / ".deploy_restart"
LAST_GOOD_COMMIT_FILE = _root / ".last_good_commit"
GRACE_PERIOD_SECONDS = 60


def send_telegram_alert(message: str) -> None:
    """Send alert to Telegram via raw HTTP request."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"Alert (not sent): {message}")
        return

    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }, timeout=10)
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")


def get_last_good_commit() -> str:
    """Read last good commit from file."""
    if LAST_GOOD_COMMIT_FILE.exists():
        return LAST_GOOD_COMMIT_FILE.read_text().strip()
    return ""


def git_checkout(commit: str) -> bool:
    """Checkout a commit via git."""
    try:
        result = subprocess.run(
            ["git", "checkout", commit],
            cwd=_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Git checkout failed: {e}")
        return False


def main():
    """Main watchdog loop."""
    print("PrivyBot launch watchdog starting...")

    while True:
        # Check if this is a deploy restart
        was_deploy = DEPLOY_RESTART_FLAG.exists()
        if was_deploy:
            DEPLOY_RESTART_FLAG.unlink()
            print("Deploy restart detected, watching for crashes...")

        start_time = time.time()

        # Start privybot.py as subprocess
        print(f"Starting privybot.py (deploy={was_deploy})...")
        try:
            result = subprocess.run(
                ["uv", "run", "python", "privybot.py"],
                cwd=_root,
            )
            exit_code = result.returncode
        except KeyboardInterrupt:
            print("Interrupted by user, exiting watchdog.")
            break
        except Exception as e:
            print(f"Failed to start privybot.py: {e}")
            exit_code = -1

        uptime = time.time() - start_time
        print(f"privybot.py exited (code={exit_code}, uptime={uptime:.1f}s)")

        # Check for bad deploy (crash within grace period after deploy)
        if was_deploy and uptime < GRACE_PERIOD_SECONDS:
            last_good = get_last_good_commit()
            if last_good:
                print(f"Bad deploy detected (uptime {uptime:.1f}s < {GRACE_PERIOD_SECONDS}s)")
                print(f"Reverting to last good commit: {last_good[:7]}")
                if git_checkout(last_good):
                    alert = f"⚠️ Deploy failed — reverted to {last_good[:7]}"
                    send_telegram_alert(alert)
                    print(alert)
                else:
                    alert = f"⚠️ Deploy failed — revert failed for {last_good[:7]}"
                    send_telegram_alert(alert)
                    print(alert)
            else:
                alert = f"⚠️ Deploy failed (no last good commit to revert to)"
                send_telegram_alert(alert)
                print(alert)

        # Brief pause before restart
        time.sleep(2)


if __name__ == "__main__":
    main()
