"""JWT token generation and validation for MCP SSE transport."""

import os
from datetime import datetime, timedelta
from typing import Optional

import jwt


# JWT secret from environment
JWT_SECRET = os.getenv("MCP_JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("MCP_JWT_SECRET not set in environment")

# JWT algorithm
ALGORITHM = "HS256"


def generate_token(expiry_minutes: int = 60) -> str:
    """Generate a short-lived JWT token for MCP access.

    Args:
        expiry_minutes: Token validity in minutes (default: 60)

    Returns:
        JWT token string
    """
    now = datetime.utcnow()
    exp = now + timedelta(minutes=expiry_minutes)

    payload = {
        "iat": now,
        "exp": exp,
        "scope": "mcp_access",
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def validate_token(token: str) -> Optional[dict]:
    """Validate a JWT token and return its payload if valid.

    Args:
        token: JWT token string

    Returns:
        Token payload dict if valid, None if invalid/expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def validate_bearer_token(auth_header: str) -> Optional[dict]:
    """Validate Authorization: Bearer <token> header.

    Args:
        auth_header: Authorization header value

    Returns:
        Token payload dict if valid, None if invalid
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ", 1)[1]
    return validate_token(token)
