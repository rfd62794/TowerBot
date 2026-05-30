"""Gmail tool functions — read-only inbox access."""

from tools.api.gmail_api import (
    get_unread_count,
    search_messages,
    get_recent_unread,
    get_messages_from,
    get_message_body,
)


def get_inbox_summary() -> dict:
    """Unread count plus up to 3 recent unread messages."""
    count = get_unread_count()
    recent = get_recent_unread(max_results=3)
    return {
        "unread_count": count,
        "recent": recent,
        "has_unread": count > 0,
    }


def search_email(query: str, max_results: int = 5) -> dict:
    """Search emails using Gmail query syntax."""
    messages = search_messages(query, max_results=max_results)
    return {
        "query": query,
        "count": len(messages),
        "messages": messages,
    }


def check_sender(sender: str, unread_only: bool = True) -> dict:
    """Check for emails from a specific sender."""
    messages = get_messages_from(sender, max_results=5, unread_only=unread_only)
    return {
        "sender": sender,
        "count": len(messages),
        "has_messages": len(messages) > 0,
        "messages": messages,
    }


def read_email(message_id: str) -> dict:
    """Get full email body and metadata for a specific message ID."""
    try:
        from tools.api.gmail_api import _get_gmail_client, _parse_message_metadata, _extract_body
        client = _get_gmail_client()
        msg = client.users().messages().get(
            userId="me",
            id=message_id,
            format="full",
        ).execute()
        meta = _parse_message_metadata(msg)
        body = _extract_body(msg.get("payload", {}))[:2000]
        return {
            "id": message_id,
            "from": meta.get("from", ""),
            "subject": meta.get("subject", ""),
            "date": meta.get("date", ""),
            "body": body,
        }
    except Exception as e:
        return {"id": message_id, "error": str(e)}
