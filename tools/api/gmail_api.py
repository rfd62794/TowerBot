"""Gmail API client — raw API calls only. Read-only, no send path."""

import base64

from googleapiclient.discovery import build
from tools.api.youtube_api import _get_credentials


def _get_gmail_client():
    creds = _get_credentials()
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _parse_message_metadata(msg: dict) -> dict:
    headers = {
        h["name"]: h["value"]
        for h in msg.get("payload", {}).get("headers", [])
    }
    return {
        "id": msg["id"],
        "thread_id": msg.get("threadId", ""),
        "from": headers.get("From", ""),
        "subject": headers.get("Subject", ""),
        "date": headers.get("Date", ""),
        "snippet": msg.get("snippet", ""),
        "unread": "UNREAD" in msg.get("labelIds", []),
    }


def _extract_body(payload: dict) -> str:
    """Extract plain text body from a message payload, handling multipart."""
    body_data = payload.get("body", {}).get("data", "")
    if body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        for subpart in part.get("parts", []):
            if subpart.get("mimeType") == "text/plain":
                data = subpart.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    return ""


def get_unread_count(label: str = "INBOX") -> int:
    try:
        client = _get_gmail_client()
        result = client.users().labels().get(userId="me", id=label).execute()
        return result.get("messagesUnread", 0)
    except Exception:
        return 0


def search_messages(query: str, max_results: int = 10) -> list[dict]:
    try:
        client = _get_gmail_client()
        result = client.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results,
        ).execute()
        message_ids = [m["id"] for m in result.get("messages", [])]
        if not message_ids:
            return []

        messages = []
        for msg_id in message_ids[:max_results]:
            detail = client.users().messages().get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            messages.append(_parse_message_metadata(detail))
        return messages
    except Exception:
        return []


def get_message_body(message_id: str) -> str:
    try:
        client = _get_gmail_client()
        msg = client.users().messages().get(
            userId="me",
            id=message_id,
            format="full",
        ).execute()
        return _extract_body(msg.get("payload", {}))[:2000]
    except Exception:
        return ""


def get_recent_unread(max_results: int = 5) -> list[dict]:
    return search_messages("is:unread in:inbox", max_results=max_results)


def get_messages_from(
    sender: str,
    max_results: int = 5,
    unread_only: bool = False,
) -> list[dict]:
    query = f"from:{sender}"
    if unread_only:
        query += " is:unread"
    return search_messages(query, max_results=max_results)
