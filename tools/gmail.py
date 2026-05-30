"""Gmail tool functions — read-only inbox access."""

from tools.api.gmail_api import (
    get_unread_count,
    search_messages,
    get_recent_unread,
    get_messages_from,
    get_message_body,
)


def get_inbox_summary(account: str = "personal") -> dict:
    """Unread count plus up to 3 recent unread messages for one account."""
    count = get_unread_count(account=account)
    recent = get_recent_unread(max_results=3, account=account)
    return {
        "unread_count": count,
        "recent": recent,
        "has_unread": count > 0,
    }


def get_all_inbox_summary() -> dict:
    """Unread counts and recent messages from both personal and RFD accounts."""
    personal = get_inbox_summary(account="personal")
    rfd_count = get_unread_count(account="rfd")
    rfd_recent = get_recent_unread(max_results=3, account="rfd")
    return {
        "personal": {
            "account": "cheater2478@gmail.com",
            "unread_count": personal["unread_count"],
            "recent": personal["recent"],
        },
        "professional": {
            "account": "RFDITServices@gmail.com",
            "unread_count": rfd_count,
            "recent": rfd_recent,
        },
        "total_unread": personal["unread_count"] + rfd_count,
        "rfd_available": rfd_count >= 0,
    }


def search_email(
    query: str,
    max_results: int = 5,
    account: str = "personal",
) -> dict:
    """Search emails using Gmail query syntax."""
    messages = search_messages(query, max_results=max_results, account=account)
    return {
        "query": query,
        "count": len(messages),
        "messages": messages,
    }


def check_sender(
    sender: str,
    unread_only: bool = True,
    account: str = "personal",
) -> dict:
    """Check for emails from a specific sender in one account."""
    messages = get_messages_from(
        sender, max_results=5, unread_only=unread_only, account=account
    )
    return {
        "sender": sender,
        "count": len(messages),
        "has_messages": len(messages) > 0,
        "messages": messages,
    }


def check_sender_all(sender: str, unread_only: bool = True) -> dict:
    """Check sender across both personal and RFD accounts."""
    personal = check_sender(sender, unread_only=unread_only, account="personal")
    rfd = check_sender(sender, unread_only=unread_only, account="rfd")
    all_messages = (
        [{"account": "personal", **m} for m in personal["messages"]] +
        [{"account": "rfd", **m} for m in rfd["messages"]]
    )
    return {
        "sender": sender,
        "count": len(all_messages),
        "has_messages": len(all_messages) > 0,
        "messages": all_messages,
    }


def read_email(message_id: str, account: str = "personal") -> dict:
    """Get full email body and metadata for a specific message ID."""
    try:
        from tools.api.gmail_api import _get_client, _parse_message_metadata, _extract_body
        client = _get_client(account)
        if client is None:
            return {"id": message_id, "error": "Account not authorized"}
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
