"""Gmail API client — raw API calls only. Read-only, no send path."""

import base64
import os
import logging

from googleapiclient.discovery import build
from api.google.youtube_api import _get_credentials
from api._handler import BaseAPIHandler

logger = logging.getLogger("privy.gmail_api")


class GmailAPIHandler(BaseAPIHandler):
    """Gmail API handler with caching and dual account support."""
    
    CACHE_PREFIX = "gmail"
    
    def _get_client(self, account: str = "personal"):
        """Return Gmail client for the given account ('personal' or 'rfd')."""
        if account == "rfd":
            return self._get_rfd_gmail_client()
        return self._get_gmail_client()
    
    def _get_gmail_client(self):
        creds = _get_credentials()
        return build("gmail", "v1", credentials=creds, cache_discovery=False)
    
    def _get_rfd_credentials(self):
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
    
    def _get_rfd_gmail_client(self):
        """Gmail client for RFDITServices account. Returns None if not authorized."""
        creds = self._get_rfd_credentials()
        if creds is None:
            return None
        return build("gmail", "v1", credentials=creds, cache_discovery=False)
    
    def _parse_message_metadata(self, msg: dict) -> dict:
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
    
    def _extract_body(self, payload: dict) -> str:
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
    
    def get_unread_count(self, label: str = "INBOX", account: str = "personal") -> dict:
        params_hash = self.hash(label, account)
        
        def _live() -> dict:
            client = self._get_client(account)
            if client is None:
                return {"count": 0, "account": account, "authorized": False}
            result = client.users().labels().get(userId="me", id=label).execute()
            return {"count": result.get("messagesUnread", 0), "account": account, "authorized": True}
        
        return self.call(f"unread_{account}", params_hash, _live, stale_ok=True)
    
    def search_messages(self, query: str, max_results: int = 10, account: str = "personal") -> dict:
        params_hash = self.hash(query, max_results, account)
        
        def _live() -> dict:
            client = self._get_client(account)
            if client is None:
                return {"messages": [], "account": account, "authorized": False}
            result = client.users().messages().list(
                userId="me",
                q=query,
                maxResults=max_results,
            ).execute()
            message_ids = [m["id"] for m in result.get("messages", [])]
            if not message_ids:
                return {"messages": [], "account": account, "authorized": True}
            
            messages = []
            for msg_id in message_ids[:max_results]:
                detail = client.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()
                messages.append(self._parse_message_metadata(detail))
            return {"messages": messages, "account": account, "authorized": True}
        
        return self.call(f"search_{account}", params_hash, _live, stale_ok=True)
    
    def get_message_body(self, message_id: str, account: str = "personal") -> dict:
        params_hash = self.hash(message_id, account)
        
        def _live() -> dict:
            client = self._get_client(account)
            if client is None:
                return {"body": "", "account": account, "authorized": False}
            msg = client.users().messages().get(
                userId="me",
                id=message_id,
                format="full",
            ).execute()
            text = self._extract_body(msg.get("payload", {}))[:2000]
            return {"body": text, "account": account, "authorized": True}
        
        return self.call(f"body_{account}", params_hash, _live, stale_ok=True)
    
    def get_recent_unread(self, max_results: int = 5, account: str = "personal") -> dict:
        return self.search_messages("is:unread in:inbox", max_results=max_results, account=account)
    
    def get_messages_from(self, sender: str, max_results: int = 5, unread_only: bool = False, account: str = "personal") -> dict:
        query = f"from:{sender}"
        if unread_only:
            query += " is:unread"
        return self.search_messages(query, max_results=max_results, account=account)


# Module-level instance
gmail_api = GmailAPIHandler()

# Backwards compat — callers in tools/gmail.py
def get_unread_count(label="INBOX", account="personal"):
    return gmail_api.get_unread_count(label, account)

def search_messages(query, max_results=10, account="personal"):
    return gmail_api.search_messages(query, max_results, account)

def get_message_body(message_id, account="personal"):
    return gmail_api.get_message_body(message_id, account)

def get_recent_unread(max_results=5, account="personal"):
    return gmail_api.get_recent_unread(max_results, account)

def get_messages_from(sender, max_results=5, unread_only=False, account="personal"):
    return gmail_api.get_messages_from(sender, max_results, unread_only, account)

# Backwards compat for test imports
def _get_gmail_client():
    return gmail_api._get_gmail_client()

def _get_rfd_credentials():
    return gmail_api._get_rfd_credentials()
