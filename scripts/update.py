"""Auto-update system — git-based self-update with safe restart."""

import subprocess
import os

INSTANCE_ROLE = os.environ.get("INSTANCE_ROLE", "development")


def trigger_restart():
    """Detached process survives service stop and handles restart."""
    # Restart PrivyBot
    subprocess.Popen(
        ["powershell", "-WindowStyle", "Hidden", "-Command",
         "Start-Sleep -Seconds 2; net stop PrivyBot; net start PrivyBot"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    )
    # Restart PrivybotMCP — delayed to let PrivyBot come up first
    subprocess.Popen(
        ["powershell", "-WindowStyle", "Hidden", "-Command",
         "Start-Sleep -Seconds 5; net stop PrivybotMCP; net start PrivybotMCP"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    )


async def check_for_updates(send_fn) -> str:
    """Check git remote, pull if behind, trigger restart.

    Args:
        send_fn: Async function to send Telegram messages

    Returns:
        Status message string
    """
    if INSTANCE_ROLE != "production":
        return "DONE: Skipped — not production instance"

    from infra.db.bot_state import get_dev_mode
    if get_dev_mode():
        return "DONE: Skipped — dev mode active"

    # Check remote
    subprocess.run(["git", "fetch", "origin", "main"], capture_output=True)
    local = subprocess.run(["git", "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    remote = subprocess.run(["git", "rev-parse", "origin/main"],
                            capture_output=True, text=True).stdout.strip()

    if local == remote:
        return f"DONE: Already up to date ({local[:7]})"

    # Behind — update
    await send_fn(f"🔄 Updating {local[:7]} → {remote[:7]}...")

    result = subprocess.run(
        ["git", "pull", "origin", "main"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return f"URGENT: Auto-update failed — {result.stderr[:200]}"

    # Save before dying
    from infra.db.autonomous import record_agent_action
    from infra.utils import safe_serialize
    record_agent_action(
        "auto_update",
        safe_serialize(f"Updated {local[:7]} → {remote[:7]}"),
        duration_ms=0
    )
    await send_fn(f"✅ Updated to {remote[:7]} — restarting...")

    trigger_restart()
    return f"DONE: Restarting with {remote[:7]}"
