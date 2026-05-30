"""Gmail tool functions — read-only inbox access."""

from api.google.gmail_api import (
    get_unread_count,
    search_messages,
    get_recent_unread,
    get_messages_from,
    get_message_body,
)
from tools.api._handler import BaseTool


class GmailTools(BaseTool):
    """Gmail tool wrapper with BaseTool pattern."""
    
    def get_inbox_summary(self, account: str = "personal") -> dict:
        """Unread count plus up to 3 recent unread messages for one account."""
        raw = get_unread_count(account=account)
        count = raw.get("count", 0)
        recent_raw = get_recent_unread(max_results=3, account=account)
        recent = recent_raw.get("messages", [])
        
        return self.success({
            "unread_count": count,
            "recent": recent,
            "has_unread": count > 0,
        }, stale_result=raw)
    
    def get_all_inbox_summary(self) -> dict:
        """Unread counts and recent messages from both personal and RFD accounts."""
        personal_raw = get_unread_count(account="personal")
        personal_count = personal_raw.get("count", 0)
        personal_recent_raw = get_recent_unread(max_results=3, account="personal")
        personal_recent = personal_recent_raw.get("messages", [])
        
        rfd_raw = get_unread_count(account="rfd")
        rfd_count = rfd_raw.get("count", 0)
        rfd_recent_raw = get_recent_unread(max_results=3, account="rfd")
        rfd_recent = rfd_recent_raw.get("messages", [])
        
        return self.success({
            "personal": {
                "account": "cheater2478@gmail.com",
                "unread_count": personal_count,
                "recent": personal_recent,
            },
            "professional": {
                "account": "RFDITServices@gmail.com",
                "unread_count": rfd_count,
                "recent": rfd_recent,
            },
            "total_unread": personal_count + rfd_count,
            "rfd_available": rfd_count >= 0,
        }, stale_result=personal_raw)
    
    def search_email(self, query: str, max_results: int = 5, account: str = "personal") -> dict:
        """Search emails using Gmail query syntax."""
        raw = search_messages(query, max_results=max_results, account=account)
        messages = raw.get("messages", [])
        
        return self.success({
            "query": query,
            "count": len(messages),
            "messages": messages,
        }, stale_result=raw)
    
    def check_sender(self, sender: str, unread_only: bool = True, account: str = "personal") -> dict:
        """Check for emails from a specific sender in one account."""
        raw = get_messages_from(sender, max_results=5, unread_only=unread_only, account=account)
        messages = raw.get("messages", [])
        
        return self.success({
            "sender": sender,
            "count": len(messages),
            "has_messages": len(messages) > 0,
            "messages": messages,
        }, stale_result=raw)
    
    def check_sender_all(self, sender: str, unread_only: bool = True) -> dict:
        """Check sender across both personal and RFD accounts."""
        personal_raw = get_messages_from(sender, max_results=5, unread_only=unread_only, account="personal")
        personal_messages = personal_raw.get("messages", [])
        
        rfd_raw = get_messages_from(sender, max_results=5, unread_only=unread_only, account="rfd")
        rfd_messages = rfd_raw.get("messages", [])
        
        all_messages = (
            [{"account": "personal", **m} for m in personal_messages] +
            [{"account": "rfd", **m} for m in rfd_messages]
        )
        
        return self.success({
            "sender": sender,
            "count": len(all_messages),
            "has_messages": len(all_messages) > 0,
            "messages": all_messages,
        }, stale_result=personal_raw)
    
    def read_email(self, message_id: str, account: str = "personal") -> dict:
        """Get full email body and metadata for a specific message ID."""
        try:
            from api.google.gmail_api import gmail_api
            client = gmail_api._get_client(account)
            if client is None:
                return self.error("Account not authorized")
            
            msg = client.users().messages().get(
                userId="me",
                id=message_id,
                format="full",
            ).execute()
            meta = gmail_api._parse_message_metadata(msg)
            body = gmail_api._extract_body(msg.get("payload", {}))[:2000]
            
            return self.success({
                "id": message_id,
                "from": meta.get("from", ""),
                "subject": meta.get("subject", ""),
                "date": meta.get("date", ""),
                "body": body,
            })
        except Exception as e:
            return self.error(str(e))


# Module-level instance
gmail_tools = GmailTools()

# Backwards compat
def get_inbox_summary(account: str = "personal") -> dict:
    return gmail_tools.get_inbox_summary(account)

def get_all_inbox_summary() -> dict:
    return gmail_tools.get_all_inbox_summary()

def search_email(query: str, max_results: int = 5, account: str = "personal") -> dict:
    return gmail_tools.search_email(query, max_results, account)

def check_sender(sender: str, unread_only: bool = True, account: str = "personal") -> dict:
    return gmail_tools.check_sender(sender, unread_only, account)

def check_sender_all(sender: str, unread_only: bool = True) -> dict:
    return gmail_tools.check_sender_all(sender, unread_only)

def read_email(message_id: str, account: str = "personal") -> dict:
    return gmail_tools.read_email(message_id, account)
