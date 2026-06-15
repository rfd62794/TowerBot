#!/usr/bin/env python3
"""Stdio-to-SSE MCP proxy for PrivyBot.

Bridges MCP stdio transport to SSE transport with JWT authentication.
Used by Claude Desktop to connect to the Tower MCP server.
"""

import asyncio
import json
import os
import sys
import threading
import queue
import io
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

# Force UTF-8 encoding for stdout to handle Unicode characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

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

# Read SSE URL from env var (set by wrapper) or default to localhost
SSE_URL = os.getenv("MCP_SSE_URL", "http://localhost:8090/sse")
BASE_URL = SSE_URL.replace("/sse", "")


def generate_jwt_token() -> str:
    """Generate a JWT Bearer token with 1-year expiry."""
    now = datetime.now(timezone.utc)
    payload = {
        "iat": now,
        "exp": now + timedelta(days=365),
    }
    return jwt.encode(payload, MCP_JWT_SECRET, algorithm="HS256")


def read_stdin_thread(message_queue: queue.Queue):
    """Thread function to read from stdin and put messages in queue."""
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            message = line.strip()
            if message:
                message_queue.put(message)
    except Exception as e:
        print(f"Stdin thread error: {e}", file=sys.stderr)


async def process_stdin_queue(session: aiohttp.ClientSession, headers: dict, endpoint_url: str, message_queue: queue.Queue):
    """Process messages from stdin queue and POST to messages endpoint."""
    while True:
        try:
            # Non-blocking check for messages
            message = message_queue.get_nowait()
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
        except queue.Empty:
            # No messages, sleep briefly
            await asyncio.sleep(0.01)
        except Exception as e:
            print(f"Queue processing error: {e}", file=sys.stderr)
            await asyncio.sleep(0.01)


async def sse_reader(resp, endpoint_event: asyncio.Event, endpoint_holder: list, headers: dict):
    """Read SSE events, capture endpoint, forward JSON-RPC messages to stdout."""
    current_event_type = None

    try:
        async for line in resp.content:
            decoded = line.decode("utf-8").rstrip("\n\r")

            if decoded.startswith("event: "):
                current_event_type = decoded[7:]

            elif decoded.startswith("data: "):
                data = decoded[6:]  # Remove "data: " prefix

                if current_event_type == "endpoint":
                    # Capture the messages endpoint URL
                    endpoint_url = urljoin(BASE_URL, data)
                    endpoint_holder.append(endpoint_url)
                    print(f"Proxy: Connected to {endpoint_url}", file=sys.stderr, flush=True)
                    endpoint_event.set()

                elif data:
                    # Only forward valid JSON-RPC messages
                    try:
                        parsed = json.loads(data)
                        # Check if it looks like a JSON-RPC response (has jsonrpc field)
                        if isinstance(parsed, dict) and "jsonrpc" in parsed:
                            print(data, flush=True)
                    except json.JSONDecodeError:
                        # Not valid JSON, skip (could be endpoint path, etc.)
                        pass

            elif decoded == "":
                # Empty line marks end of event
                current_event_type = None
    except Exception as e:
        print(f"SSE reader error: {e}", file=sys.stderr, flush=True)


async def stdio_to_sse_bridge():
    """Bridge stdin ↔ SSE bidirectionally."""
    token = generate_jwt_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Create queue for stdin messages
    message_queue = queue.Queue()

    # Start stdin reading thread
    stdin_thread = threading.Thread(target=read_stdin_thread, args=(message_queue,), daemon=True)
    stdin_thread.start()

    async with aiohttp.ClientSession() as session:
        # Single SSE connection
        async with session.get(SSE_URL, headers=headers) as resp:
            endpoint_event = asyncio.Event()
            endpoint_holder = []

            # Start SSE reader in background
            sse_task = asyncio.create_task(sse_reader(resp, endpoint_event, endpoint_holder, headers))

            # Wait for endpoint
            try:
                await asyncio.wait_for(endpoint_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                print("Error: No endpoint received from SSE within 10s", file=sys.stderr, flush=True)
                sys.exit(1)

            endpoint_url = endpoint_holder[0]

            # Start stdin processor
            stdin_task = asyncio.create_task(process_stdin_queue(session, headers, endpoint_url, message_queue))

            # Wait for both tasks
            try:
                await asyncio.gather(sse_task, stdin_task, return_exceptions=True)
            except Exception as e:
                print(f"Bridge error: {e}", file=sys.stderr, flush=True)


async def main():
    """Main entry point."""
    try:
        await stdio_to_sse_bridge()
    except Exception as e:
        print(f"Proxy error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
