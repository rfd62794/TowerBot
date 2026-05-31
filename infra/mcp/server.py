"""Unified MCP server supporting stdio and SSE transports.

Exposes curated PrivyBot tools via MCP for Claude (Desktop and claude.ai).
"""

import argparse
import asyncio
import inspect
import json
import logging
import os
import sys
from pathlib import Path

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

# Add project root to path for imports
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env")

from infra.mcp.config import MCP_EXPOSED_TOOLS, MCP_FAST_VARIANTS
from tools.registry import TOOL_REGISTRY
from infra.db.schema import init_db

# Initialize database before server starts
init_db()

# Optional JWT auth for SSE
try:
    from api.mcp.auth import validate_bearer_token
    JWT_AUTH_AVAILABLE = True
except ImportError:
    JWT_AUTH_AVAILABLE = False
    logging.warning("JWT auth not available — SSE transport will be unauthenticated")

logger = logging.getLogger("privy.mcp")

# Create MCP server
server = Server("privybot")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List all exposed MCP tools."""
    tools = []
    for name in MCP_EXPOSED_TOOLS:
        if name not in TOOL_REGISTRY:
            logger.warning(f"Tool {name} in MCP_EXPOSED_TOOLS but not in TOOL_REGISTRY")
            continue

        definition = TOOL_REGISTRY[name]["definition"]
        tools.append(types.Tool(
            name=name,
            description=definition["function"]["description"],
            inputSchema=definition["function"]["parameters"],
        ))

    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Execute a tool call with fast-first routing and timeout protection."""
    if name not in MCP_EXPOSED_TOOLS:
        raise ValueError(f"Tool {name} is not exposed via MCP")

    if name not in TOOL_REGISTRY:
        raise ValueError(f"Tool {name} not found in TOOL_REGISTRY")

    # Fast-first routing: try fast variant if available
    fast_fn = MCP_FAST_VARIANTS.get(name)
    if fast_fn:
        try:
            result = fast_fn(**arguments)
            if result and isinstance(result, dict) and result.get("ok"):
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, default=str),
                )]
        except Exception as e:
            logger.warning(f"Fast variant failed for {name}: {e}, falling back to full tool")

    # Full tool execution with timeout
    fn = TOOL_REGISTRY[name]["fn"]
    
    def run_tool():
        result = fn(**arguments)
        if inspect.iscoroutine(result):
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(result)
        return result

    try:
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, run_tool),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "ok": False,
                "error": f"{name} timed out after 30s — try a more specific query"
            })
        )]

    return [types.TextContent(
        type="text",
        text=json.dumps(result, default=str),
    )]


async def run_stdio():
    """Run MCP server with stdio transport (Claude Desktop)."""
    logger.info("Starting MCP server with stdio transport")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


async def run_sse(port: int = 8090):
    """Run MCP server with SSE transport (remote via Tailscale)."""
    logger.info(f"Starting MCP server with SSE transport on port {port}")

    # Create SSE transport
    sse = SseServerTransport("/messages/")

    # SSE endpoint handler
    async def handle_sse(request: Request) -> Response:
        # JWT auth check if available
        if JWT_AUTH_AVAILABLE:
            auth_header = request.headers.get("Authorization")
            if not validate_bearer_token(auth_header):
                return Response("Unauthorized", status_code=401)

        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
        return Response()

    # Create Starlette app
    app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    # Run with uvicorn
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server_instance = uvicorn.Server(config)
    await server_instance.serve()


def main():
    """Entry point — select transport via CLI flag."""
    parser = argparse.ArgumentParser(description="PrivyBot MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport layer: stdio (Claude Desktop) or sse (remote)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8090,
        help="Port for SSE transport (default: 8090)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        anyio.run(run_stdio)
    else:
        anyio.run(run_sse, args.port)


if __name__ == "__main__":
    main()
