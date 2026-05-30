"""Gmail API client — raw API calls only. Read-only, no send path."""

import base64
import os

from googleapiclient.discovery import build
from tools.api.youtube_api import _get_credentials


def _get_gmail_client():
    creds = _get_credentials()
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _get_rfd_credentials():
    """Load RFD IT Services credentials. Returns None if token not present."""
    rfd_token = os.getenv("RFD_GMAIL_TOKEN_PATH", "config/rfd_token.json")
    if not os.path.exists(rfd_token):
        return None
    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(rfd_token)
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        return creds
    except Exception:
        return None


def _get_rfd_gmail_client():
    """Gmail client for RFDITServices account. Returns None if not authorized."""
    creds = _get_rfd_credentials()
    if creds is None:
        return None
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _get_client(account: str = "personal"):
    """Return Gmail client for the given account ('personal' or 'rfd')."""
    if account == "rfd":
        return _get_rfd_gmail_client()
    return _get_gmail_client()


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


def get_unread_count(label: str = "INBOX", account: str = "personal") -> int:
    try:
        client = _get_client(account)
        if client is None:
            return 0
        result = client.users().labels().get(userId="me", id=label).execute()
        return result.get("messagesUnread", 0)
    except Exception:
        return 0


def search_messages(
    query: str,
    max_results: int = 10,
    account: str = "personal",
) -> list[dict]:
    try:
        client = _get_client(account)
        if client is None:
            return []
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


def get_message_body(message_id: str, account: str = "personal") -> str:
    try:
        client = _get_client(account)
        if client is None:
            return ""
        msg = client.users().messages().get(
            userId="me",
            id=message_id,
            format="full",
        ).execute()
        return _extract_body(msg.get("payload", {}))[:2000]
    except Exception:
        return ""


def get_recent_unread(
    max_results: int = 5,
    account: str = "personal",
) -> list[dict]:
    return search_messages("is:unread in:inbox", max_results=max_results, account=account)


def get_messages_from(
    sender: str,
    max_results: int = 5,
    unread_only: bool = False,
    account: str = "personal",
) -> list[dict]:
    query = f"from:{sender}"
    if unread_only:
        query += " is:unread"
    return search_messages(query, max_results=max_results, account=account)
