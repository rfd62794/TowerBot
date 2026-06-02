"""
Approval listener management.
Creates and reads approval_listeners rows.
Constructs Telegram approval messages — does not send them.
Sending is the bot layer's responsibility.
"""
import uuid
from datetime import datetime, timezone, timedelta
from infra.db.schema import _exec


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


DEFAULT_EXPIRY_HOURS = 48


def create_listener(chain_id: str, step_id: str,
                    telegram_chat_id: str,
                    expires_hours: int = DEFAULT_EXPIRY_HOURS) -> dict:
    """
    Create an approval listener row.
    Returns the created listener dict.
    """
    listener_id = _uuid()
    now = _now()
    expires_at = (datetime.now(timezone.utc) +
                  timedelta(hours=expires_hours)).isoformat()

    _exec(
        """INSERT INTO approval_listeners
           (id, chain_id, step_id, telegram_chat_id,
            expires_at, status)
           VALUES (?, ?, ?, ?, ?, 'waiting')""",
        (listener_id, chain_id, step_id, telegram_chat_id, expires_at),
        commit=True
    )
    return get_listener(listener_id)


def get_listener(listener_id: str) -> dict | None:
    """Fetch a listener by ID."""
    row = _exec(
        "SELECT * FROM approval_listeners WHERE id=?",
        (listener_id,)
    ).fetchone()
    return dict(row) if row else None


def get_waiting_listener_for_chain(chain_id: str) -> dict | None:
    """Find the active waiting listener for a chain."""
    row = _exec(
        """SELECT * FROM approval_listeners
           WHERE chain_id=? AND status='waiting'
           ORDER BY expires_at ASC LIMIT 1""",
        (chain_id,)
    ).fetchone()
    return dict(row) if row else None


def resolve_listener(listener_id: str, response: str,
                     message_id: str = None) -> None:
    """
    Mark a listener resolved with the given response.
    response: 'approved' | 'rejected' | 'expired'
    """
    _exec(
        """UPDATE approval_listeners
           SET status='resolved', response=?, message_id=?
           WHERE id=?""",
        (response, message_id, listener_id),
        commit=True
    )


def build_approval_message(chain_id: str, step_name: str,
                           payload_summary: str,
                           listener_id: str) -> dict:
    """
    Build a Telegram message dict with inline keyboard.
    Returns a dict ready to pass to the bot's send_message.
    The callback_data encodes listener_id for the router to match.

    Structure:
      text: human-readable approval request
      reply_markup: inline keyboard with Approve / Reject buttons
    """
    text = (
        f"⏸ <b>Approval needed</b>\n\n"
        f"<b>Step:</b> {step_name}\n"
        f"<b>Chain:</b> <code>{chain_id[:8]}</code>\n\n"
        f"{payload_summary}\n\n"
        f"<i>Expires in {DEFAULT_EXPIRY_HOURS}h</i>"
    )

    reply_markup = {
        "inline_keyboard": [[
            {
                "text": "✅ Approve",
                "callback_data": f"approval:approve:{listener_id}"
            },
            {
                "text": "❌ Reject",
                "callback_data": f"approval:reject:{listener_id}"
            }
        ]]
    }

    return {"text": text, "reply_markup": reply_markup, "parse_mode": "HTML"}
