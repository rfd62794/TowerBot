# MCP Dual-Transport Server

Build a unified MCP server supporting both stdio (Claude Desktop local) and SSE (remote via Tailscale) transports from a single codebase. The server exposes a curated subset of PrivyBot's 46 tools via MCP, enabling Claude (both Desktop and claude.ai) to call PrivyBot tools directly. Local access uses stdio with no auth; remote access uses FastAPI SSE with JWT middleware.

## Architecture

**Single server, two transports:**
- `infra/mcp/server.py` — unified MCP server using official MCP Python SDK
- `--transport stdio` — Claude Desktop, local, no auth (immediate use)
- `--transport sse` — FastAPI SSE, remote, JWT auth (Tower deployment)

**Tool exposure:**
- `MCP_EXPOSED_TOOLS` curated set in `infra/mcp/config.py`
- Manual configuration (not marker classes) — faster to build, clean upgrade path
- Excludes: internal tools (think, name_thread, audit_repo_compliance)
- Includes: memory, calendar, email, itch, YouTube, blog, reddit, games

**Auth (SSE only):**
- `api/mcp/auth.py` — JWT token generation/validation
- `/mcp_token` Telegram command — generates short-lived tokens (15m/1h/24h)
- JWT middleware on SSE transport path only

**Remote access (Tower):**
- Tailscale Funnel: `tailscale funnel --bg 8090`
- Public HTTPS URL: `https://nitro.ts.net/mcp`
- Claude connects via URL + token

## Implementation Steps

1. **Update ADR-033** — reflect dual-transport decision (stdio now, SSE later)
2. **uv add mcp PyJWT** — install MCP SDK and JWT library
3. **Add MCP_JWT_SECRET to .env and .env.example** — secret key for JWT validation
4. **Create `infra/mcp/config.py`** — MCP_EXPOSED_TOOLS curated set
5. **Create `api/mcp/auth.py`** — JWT token generation/validation middleware
6. **Create `infra/mcp/server.py`** — unified MCP server with dual transports
   - Read MCP SDK docs/source before implementing transport layer (don't guess API)
   - stdio_server() for Claude Desktop
   - SseServerTransport + FastAPI for remote
   - Tool registry → MCP schema converter
   - Tool execution wrapper with async/sync handling (inspect.iscoroutine())
7. **Add `/mcp_token` command** — Telegram command to generate JWT tokens
8. **Add Claude Desktop config to README.md** — stdio setup instructions
9. **Write tests** — 6 new tests (318 + 6 = 324 total)
   - test_mcp_tool_listing_returns_schema
   - test_mcp_tool_execution_calls_correct_fn
   - test_mcp_tool_not_in_exposed_set_raises
   - test_jwt_generate_and_validate
   - test_jwt_expired_token_rejected
   - test_jwt_invalid_token_rejected
10. **Add Tailscale Funnel docs** — remote access setup instructions

## Key Decisions

- **Unified server:** One codebase, transport selected at startup via flag
- **Manual tool curation:** MCP_EXPOSED_TOOLS set (not marker classes)
- **Auth on SSE only:** stdio path has no middleware (local-only)
- **TOOL_REGISTRY as source:** Single source of truth, converter function
- **JWT short-lived:** 15m/1h/24h options, generated via Telegram

## Claude Desktop Config (stdio)

```json
{
  "mcpServers": {
    "privybot": {
      "command": "uv",
      "args": ["run", "python", "infra/mcp/server.py", "--transport", "stdio"],
      "cwd": "C:/Github/PrivyBot"
    }
  }
}
```

## Remote Startup (SSE)

```bash
uv run python infra/mcp/server.py --transport sse --port 8090
tailscale funnel --bg 8090
```

## MCP_EXPOSED_TOOLS (initial)

- Memory: save_memory, update_memory, retire_memory, get_memories
- Calendar: get_today_schedule, get_upcoming_events, check_availability
- Email: get_inbox_summary, search_email, check_sender_all
- Games: get_itch_stats, get_game_metrics, get_content_recommendations
- YouTube: get_youtube_stats, get_top_videos, get_video_analytics
- Blog: get_blog_posts, create_blog_draft
- Reddit: reddit_search
- Search: web_search, wiki_lookup

(Excludes: think, name_thread, audit_repo_compliance, internal tools)
