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

Install as a Windows service:

```powershell
nssm install PrivyBot "C:\Path\To\python.exe" "C:\Github\PrivyBot\privybot.py"
nssm set PrivyBot AppDirectory "C:\Github\PrivyBot"
nssm start PrivyBot
```

## License

MIT
