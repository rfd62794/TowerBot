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

import aiohttp
import jwt
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

MCP_JWT_SECRET = os.getenv("MCP_JWT_SECRET")
if not MCP_JWT_SECRET:
    print("Error: MCP_JWT_SECRET not found in .env", file=sys.stderr)
    sys.exit(1)

SSE_URL = "http://localhost:8090/sse"


def generate_jwt_token() -> str:
    """Generate a JWT Bearer token with 1-year expiry."""
    now = datetime.now(timezone.utc)
    payload = {
        "iat": now,
        "exp": now + timedelta(days=365),
    }
    return jwt.encode(payload, MCP_JWT_SECRET, algorithm="HS256")


async def stdin_to_sse(session: aiohttp.ClientSession, headers: dict):
    """Read JSON-RPC from stdin and POST to SSE endpoint."""
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    async for line in reader:
        message = line.decode("utf-8").strip()
        if message:
            try:
                await session.post(
                    SSE_URL,
                    headers={**headers, "Content-Type": "application/json"},
                    data=message.encode("utf-8"),
                )
            except Exception as e:
                print(f"Error sending message: {e}", file=sys.stderr)


async def sse_to_stdout(session: aiohttp.ClientSession, headers: dict):
    """Read SSE events and forward to stdout."""
    async with session.get(SSE_URL, headers=headers) as resp:
        async for line in resp.content:
            decoded = line.decode("utf-8").strip()
            if decoded.startswith("data: "):
                data = decoded[6:]  # Remove "data: " prefix
                if data:
                    print(data, flush=True)


async def stdio_to_sse_bridge():
    """Bridge stdin ↔ SSE bidirectionally."""
    token = generate_jwt_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession() as session:
        # Run both directions concurrently
        await asyncio.gather(
            stdin_to_sse(session, headers),
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
