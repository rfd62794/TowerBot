# PrivyBot

Robert Floyd Dugger's personal AI assistant — a single-file Telegram bot that
routes messages to OpenRouter, holds conversation context in SQLite, manages its
own memory via tool calling, reports memory operations to Telegram, and names
threads automatically.

## Features

- **OpenRouter routing** via the OpenAI client (default free Llama, DeepSeek, Claude Sonnet).
- **SQLite context** (`privy.db`): threads, messages, memory.
- **Self-managed memory** through four agent tools: `save_memory`, `update_memory`, `get_memories`, `name_thread`.
- **Telegram report layer** — every memory op is announced ("📝 Noted", "✏️ Updated", "📎 Thread").
- **Automatic thread naming** after the first response.
- **First-run bootstrap** — send a context document and the bot (using Claude) learns who you are.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # then fill in your keys
python privybot.py
```

## Environment (`.env`)

| Key | Purpose |
|-----|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your chat ID (only this chat is served) |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `DEFAULT_MODEL` | Free model for normal messages |
| `DEEP_MODEL` | Model for `/think` |
| `CLAUDE_MODEL` | Model for `/claude` and bootstrap |
| `PRIVY_NAME` | Bot persona name |

## Commands

| Command | Action |
|---------|--------|
| `/new` | New thread (memory preserved) |
| `/memories` | List active memories by layer |
| `/think <msg>` | Route to DeepSeek |
| `/claude <msg>` | Route to Claude Sonnet |
| `/help` | List commands |
| _any text_ | Default free model |

## Deploy (Tower / NSSM)

See [docs/TOWER_DEPLOY.md](docs/TOWER_DEPLOY.md) for detailed deployment instructions.

Quick install:

```powershell
nssm install PrivyBot "C:\Path\To\python.exe" "-m uv run python privybot.py"
nssm set PrivyBot AppDirectory "C:\Github\PrivyBot"
nssm start PrivyBot
```

## Development Workflow

Branches:
- `main` — Tower production, never commit directly
- `dev` — active development on laptop
- `experimental` — risky ideas, may never merge

Standard workflow:
```bash
git checkout dev
# [make changes]
uv run python scripts/verify.py
git checkout main
git merge dev
git push origin main
# /deploy from Telegram
```

Hotfix workflow:
```bash
git checkout main
git checkout -b hotfix/description
# [fix the issue]
uv run python scripts/verify.py
git checkout main
git merge hotfix/description
git push origin main
# /deploy from Telegram
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Layered architecture and import rules
- [docs/TOWER_DEPLOY.md](docs/TOWER_DEPLOY.md) — Windows tower deployment with NSSM
- [docs/TOOLS.md](docs/TOOLS.md) — How to add new tools
- [docs/adr/ADR-033.md](docs/adr/ADR-033.md) — MCP server architecture

## MCP Server (Model Context Protocol)

PrivyBot exposes tools via MCP for Claude (Desktop and claude.ai). This enables direct tool calls from Claude conversations without manual context switching.

### Claude Desktop (stdio transport)

Edit `~/.config/claude/claude_desktop_config.json` (Linux/macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

Restart Claude Desktop. PrivyBot tools are now available in any Claude Desktop conversation.

### Remote Access (SSE transport + Tailscale)

**Prerequisites:**
- Tailscale installed and logged in on the machine running PrivyBot
- `MCP_JWT_SECRET` set in `.env`

**Setup:**

```bash
# 1. Generate JWT token via Telegram
/mcp_token 1h  # Options: 15m, 1h, 24h

# 2. Start MCP server with SSE transport
uv run python infra/mcp/server.py --transport sse --port 8090

# 3. Expose via Tailscale Funnel (runs in background)
tailscale funnel --bg 8090

# 4. Get your Tailscale Funnel URL
tailscale funnel status
# Returns: https://<tailnet-name>.ts.net
```

**Connecting from claude.ai:**
- URL: `https://<tailnet-name>.ts.net/sse`
- Headers: `Authorization: Bearer <token>`

**Stopping the server:**
```bash
# Stop Tailscale Funnel
tailscale funnel --bg --reset 8090

# Stop MCP server (Ctrl+C in the terminal)
```

**Notes:**
- Tailscale Funnel requires a Tailscale account with Funnel enabled
- The URL is persistent as long as Funnel is running
- JWT tokens expire automatically — regenerate via `/mcp_token`

### Exposed Tools

A curated subset of tools is exposed via MCP (see `infra/mcp/config.py`). Includes memory, calendar, email, games, YouTube, blog, reddit, and search tools. Internal tools (think, name_thread, audit) are excluded.

## License

MIT
