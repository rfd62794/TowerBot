#!/usr/bin/env python3
"""Stdio-to-SSE MCP proxy for PrivyBot.

Bridges MCP stdio transport to SSE transport with JWT authentication.
Used by Claude Desktop to connect to the Tower MCP server.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

# Change to script directory so relative paths work
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import aiohttp
import jwt
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

MCP_JWT_SECRET = os.getenv("MCP_JWT_SECRET")
if not MCP_JWT_SECRET:
    print("Error: MCP_JWT_SECRET not found in .env", file=sys.stderr)
    sys.exit(1)

BASE_URL = "http://localhost:8090"
SSE_URL = f"{BASE_URL}/sse"


def generate_jwt_token() -> str:
    """Generate a JWT Bearer token with 1-year expiry."""
    now = datetime.now(timezone.utc)
    payload = {
        "iat": now,
        "exp": now + timedelta(days=365),
    }
    return jwt.encode(payload, MCP_JWT_SECRET, algorithm="HS256")


async def stdin_to_messages(session: aiohttp.ClientSession, headers: dict, endpoint_url: str):
    """Read JSON-RPC from stdin and POST to messages endpoint."""
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    async for line in reader:
        message = line.decode("utf-8").strip()
        if message:
            try:
                # Validate it's JSON before sending
                json.loads(message)
                await session.post(
                    endpoint_url,
                    headers={**headers, "Content-Type": "application/json"},
                    data=message.encode("utf-8"),
                )
            except json.JSONDecodeError:
                # Not valid JSON, skip
                pass
            except Exception as e:
                print(f"Error sending message: {e}", file=sys.stderr)


async def sse_to_stdout(session: aiohttp.ClientSession, headers: dict):
    """Read SSE events, capture endpoint, forward JSON-RPC messages to stdout."""
    endpoint_url = None

    async with session.get(SSE_URL, headers=headers) as resp:
        current_event_type = None

        async for line in resp.content:
            decoded = line.decode("utf-8").rstrip("\n\r")

            if decoded.startswith("event: "):
                current_event_type = decoded[7:]

            elif decoded.startswith("data: "):
                data = decoded[6:]  # Remove "data: " prefix

                if current_event_type == "endpoint":
                    # Capture the messages endpoint URL
                    endpoint_url = urljoin(BASE_URL, data)
                    print(f"Proxy: Connected to {endpoint_url}", file=sys.stderr)

                elif data:
                    # Only forward valid JSON-RPC messages
                    try:
                        json.loads(data)
                        print(data, flush=True)
                    except json.JSONDecodeError:
                        # Not valid JSON, skip (could be endpoint path, etc.)
                        pass

            elif decoded == "":
                # Empty line marks end of event
                current_event_type = None

    return endpoint_url


async def stdio_to_sse_bridge():
    """Bridge stdin ↔ SSE bidirectionally."""
    token = generate_jwt_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession() as session:
        # First, connect to SSE to get the endpoint
        endpoint_url = await sse_to_stdout(session, headers)

        if not endpoint_url:
            print("Error: No endpoint received from SSE", file=sys.stderr)
            sys.exit(1)

        # Then run both directions
        await asyncio.gather(
            stdin_to_messages(session, headers, endpoint_url),
            sse_to_stdout(session, headers),
            return_exceptions=True,
        )


async def main():
    """Main entry point."""
    try:
        await stdio_to_sse_bridge()
    except Exception as e:
        print(f"Proxy error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
