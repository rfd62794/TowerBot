"""
PrivyBot — Robert Floyd Dugger's personal AI assistant.
Single-file Telegram bot: OpenRouter routing, SQLite context,
self-managed memory via tool calling, Telegram memory reports,
and automatic thread naming.

Scaffolded from PhantomArbiter (TelegramManager + Logger).
"""

import os
import sys
import json
import uuid
import queue
import asyncio
import sqlite3
import logging
import threading
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.error import BadRequest

# ═══════════════════════════════════════════════════════════════════
# LOGGER (copied from PhantomArbiter/src/shared/system/logging.py)
# ═══════════════════════════════════════════════════════════════════

from loguru import logger
from rich.logging import RichHandler
from rich.console import Console

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(LOG_DIR, f"privy_{_run_id}.log")

SOURCE_ICONS = {
    "SYSTEM": "🛸", "TG": "📡", "MEMORY": "🧠", "AGENT": "🤖",
    "THREAD": "📎", "REPORT": "📋", "MODEL": "Ⓜ️", "DB": "💾",
}


def signal_bus_sink(message):
    """Loguru sink that forwards logs to the SignalBus (no-op outside PhantomArbiter)."""
    try:
        from src.shared.system.signal_bus import signal_bus, Signal, SignalType

        record = message.record
        level = record["level"].name
        text = record["message"]

        source = "SYSTEM"
        if text.startswith("[") and "]" in text:
            source = text[1:text.index("]")].upper()
            text = text[text.index("]") + 1:].strip()

        signal_bus.emit(Signal(
            type=SignalType.LOG_UPDATE,
            source=source,
            data={"level": level, "message": text}
        ))

        from src.shared.state.app_state import state
        if level in ["INFO", "WARNING", "ERROR", "SUCCESS", "CRITICAL"]:
            state.log(f"[{source}] {text}")
        if level in ["ERROR", "CRITICAL"]:
            state.flash_error(f"[{source}] {text}")

    except Exception:
        pass


config = {
    "handlers": [
        {
            "sink": RichHandler(
                console=Console(width=120),
                rich_tracebacks=True,
                markup=True,
                show_time=True,
                show_level=True,
                show_path=False
            ),
            "format": "{message}",
            "level": "INFO",
        },
        {
            "sink": log_file,
            "format": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
            "level": "INFO",
            "rotation": "10 MB",
            "retention": "3 days",
            "compression": "zip",
        },
        {
            "sink": signal_bus_sink,
            "level": "INFO",
        }
    ]
}

logger.configure(**config)


class Logger:
    """Backward-compatible wrapper for Loguru."""

    _silent = False

    @staticmethod
    def _parse(message: str):
        if message.startswith("[") and "]" in message:
            source = message[1:message.index("]")].upper()
            icon = SOURCE_ICONS.get(source, "")
            if icon:
                return f"[dim]{icon}[/] {message}"
        return message

    @staticmethod
    def info(message: str, icon: str = ""):
        if Logger._silent: return
        msg = f"{icon} {message}" if icon else Logger._parse(message)
        logger.info(msg)

    @staticmethod
    def success(message: str):
        if Logger._silent: return
        logger.success(f"✅ {Logger._parse(message)}")

    @staticmethod
    def warning(message: str):
        if Logger._silent: return
        logger.warning(Logger._parse(message))

    @staticmethod
    def error(message: str):
        if Logger._silent: return
        logger.error(Logger._parse(message))

    @staticmethod
    def critical(message: str):
        if Logger._silent: return
        logger.critical(f"🛑 {Logger._parse(message)}")

    @staticmethod
    def debug(message: str):
        if Logger._silent: return
        logger.debug(message)

    @staticmethod
    def section(title: str):
        if Logger._silent: return
        print("\n")
        logger.opt(raw=True).info(f"<magenta bold>=== {title} ===</magenta bold>\n")


# ═══════════════════════════════════════════════════════════════════
# TELEGRAM MANAGER (stripped from PhantomArbiter)
# ═══════════════════════════════════════════════════════════════════

class TelegramManager:
    """
    Transport layer for Telegram. Stripped of trading/dashboard logic.
    - Keeps ApplicationBuilder setup, _run_async_loop, backoff, threading.
    - Keeps _simple_send() as a reliable fallback.
    - send_alert() renamed to send().
    Routes incoming text + commands to a handler object.
    """

    def __init__(self, handler=None):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.handler = handler  # object exposing on_message / on_command

        self.enabled = bool(self.token and self.chat_id)
        self.running = False

        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.application = None
        self.thread: Optional[threading.Thread] = None

        if not self.enabled:
            Logger.warning("⚠️ TG Manager: No Token/Chat. Telegram disabled.")

    def start(self):
        if not self.enabled:
            return
        if self.thread:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_async_loop, name="TelegramManager")
        self.thread.daemon = True
        self.thread.start()
        Logger.info("📡 [TG] Manager Started (Polling)")

    def stop(self):
        if not self.enabled:
            return
        Logger.info("📡 [TG] Manager Stopping...")
        # _serve() polls self.running each second and shuts down cleanly.
        self.running = False
        try:
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=10)
            self.thread = None
            Logger.info("📡 [TG] Manager Stopped.")
        except Exception as e:
            Logger.debug(f"[TG] Stop Error: {e}")

    def _run_async_loop(self):
        """Main async loop running in background thread (kept from PhantomArbiter).
        Drives the PTB lifecycle manually (initialize/start/start_polling) since
        run_polling() is not safe to call outside the main thread.

        Uses a SelectorEventLoop: on Windows the default ProactorEventLoop
        breaks async TLS via anyio/httpx (BrokenResourceError during the
        handshake), which blocks all Telegram polling. The selector loop
        connects cleanly."""
        self.loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(self.loop)

        self.application = ApplicationBuilder().token(self.token).build()
        self._register_commands()

        logging.getLogger("httpx").setLevel(logging.WARNING)

        backoff = 5

        while self.running:
            try:
                self.loop.run_until_complete(self._serve())
                break  # clean shutdown requested via stop()
            except Exception as e:
                if not self.running:
                    break
                Logger.error(f"❌ [TG] Connection Error: {e}")
                print(f"   ⚠️ [TG] Connection lost. Retrying in {backoff}s...")
                import time
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)

        try:
            self.loop.close()
        except Exception as e:
            Logger.debug(f"[TG] Cleanup error: {e}")

    async def _serve(self):
        """Manual PTB lifecycle: initialize, start, poll until stopped."""
        app = self.application
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        Logger.info("✅ [TG] Manager READY (Polling...)")
        try:
            while self.running:
                await asyncio.sleep(1)
        finally:
            try:
                await app.updater.stop()
            except Exception:
                pass
            try:
                await app.stop()
            except Exception:
                pass
            try:
                await app.shutdown()
            except Exception:
                pass

    def _register_commands(self):
        app = self.application
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("new", self._cmd_new))
        app.add_handler(CommandHandler("memories", self._cmd_memories))
        app.add_handler(CommandHandler("think", self._cmd_think))
        app.add_handler(CommandHandler("claude", self._cmd_claude))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))

    # ── PUBLIC SEND (renamed from send_alert) ────────────────────────

    def send(self, message: str):
        """Send a new message (thread-safe). Uses _simple_send as fallback."""
        if not self.enabled:
            return
        if self.loop and self.loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._async_send(message), self.loop)
                return
            except Exception as e:
                Logger.debug(f"[TG] async send failed, falling back: {e}")
        self._simple_send(message)

    def _simple_send(self, message: str):
        """Send via requests.post (blocking but reliable fallback)."""
        import requests
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            resp = requests.post(
                url,
                json={"chat_id": self.chat_id, "text": message},
                timeout=5,
            )
            if resp.status_code != 200:
                Logger.debug(f"[TG] Send failed: {resp.status_code}")
        except Exception as e:
            Logger.debug(f"[TG] Send error: {e}")

    async def _async_send(self, message: str):
        try:
            await self.application.bot.send_message(chat_id=self.chat_id, text=message)
        except Exception as e:
            Logger.debug(f"[TG] Send Error: {e}")

    # ── INCOMING HANDLERS ────────────────────────────────────────────

    def _authorized(self, update: Update) -> bool:
        return str(update.effective_chat.id) == str(self.chat_id)

    async def _dispatch(self, update, text: str, command: Optional[str], args: str):
        """Run blocking handler logic off the event loop, then reply."""
        if not self.handler:
            return
        reply = await asyncio.to_thread(
            self.handler.handle, text, command, args
        )
        if reply:
            for chunk in _chunk_text(reply):
                await update.message.reply_text(chunk)

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        await self._dispatch(update, update.message.text, None, "")

    async def _cmd_new(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        await self._dispatch(update, "", "new", "")

    async def _cmd_memories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        await self._dispatch(update, "", "memories", "")

    async def _cmd_think(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        args = " ".join(context.args) if context.args else ""
        await self._dispatch(update, args, "think", args)

    async def _cmd_claude(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        args = " ".join(context.args) if context.args else ""
        await self._dispatch(update, args, "claude", args)

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        await update.message.reply_text(
            "🤖 PrivyBot Commands\n"
            "/new — start a new conversation thread (memory kept)\n"
            "/memories — list all active memories\n"
            "/think <message> — route to DeepSeek (deep reasoning)\n"
            "/claude <message> — route to Claude Sonnet\n"
            "/help — this message\n\n"
            "Any other message uses the default free model."
        )


def _chunk_text(text: str, limit: int = 4000):
    """Split long text into Telegram-safe chunks."""
    return [text[i:i + limit] for i in range(0, len(text), limit)] or [""]


# ═══════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "privy.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    name TEXT,
    created DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT,
    role TEXT,
    content TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (thread_id) REFERENCES threads(id)
);

CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE,
    content TEXT,
    layer TEXT,
    created DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    active INTEGER DEFAULT 1
);
"""


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        Logger.info("💾 [DB] Connected: privy.db")

    def _exec(self, sql: str, params=(), commit=False):
        with self._lock:
            cur = self._conn.execute(sql, params)
            if commit:
                self._conn.commit()
            return cur

    # ── threads ──
    def create_thread(self, name: Optional[str] = None) -> str:
        tid = str(uuid.uuid4())
        self._exec(
            "INSERT INTO threads (id, name) VALUES (?, ?)",
            (tid, name), commit=True
        )
        return tid

    def touch_thread(self, tid: str):
        self._exec(
            "UPDATE threads SET last_active = CURRENT_TIMESTAMP WHERE id = ?",
            (tid,), commit=True
        )

    def set_thread_name(self, tid: str, name: str):
        self._exec(
            "UPDATE threads SET name = ? WHERE id = ?",
            (name, tid), commit=True
        )

    def thread_name(self, tid: str) -> Optional[str]:
        row = self._exec("SELECT name FROM threads WHERE id = ?", (tid,)).fetchone()
        return row["name"] if row else None

    # ── messages ──
    def add_message(self, tid: str, role: str, content: str):
        self._exec(
            "INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)",
            (tid, role, content), commit=True
        )
        self.touch_thread(tid)

    def last_messages(self, tid: str, n: int = 10):
        rows = self._exec(
            "SELECT role, content FROM messages WHERE thread_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (tid, n)
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def message_count(self, tid: str) -> int:
        row = self._exec(
            "SELECT COUNT(*) c FROM messages WHERE thread_id = ?", (tid,)
        ).fetchone()
        return row["c"] if row else 0

    # ── memory ──
    def memory_empty(self) -> bool:
        row = self._exec("SELECT COUNT(*) c FROM memory").fetchone()
        return (row["c"] if row else 0) == 0

    def active_memories(self):
        rows = self._exec(
            "SELECT key, content, layer FROM memory WHERE active = 1 ORDER BY layer, key"
        ).fetchall()
        return [dict(r) for r in rows]

    def save_memory(self, key: str, content: str, layer: str):
        self._exec(
            "INSERT INTO memory (key, content, layer) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET content=excluded.content, "
            "layer=excluded.layer, updated=CURRENT_TIMESTAMP, active=1",
            (key, content, layer), commit=True
        )

    def update_memory(self, key: str, content: str):
        cur = self._exec(
            "UPDATE memory SET content = ?, updated = CURRENT_TIMESTAMP "
            "WHERE key = ?",
            (content, key), commit=True
        )
        if cur.rowcount == 0:
            # Treat as a save if key didn't exist yet.
            self.save_memory(key, content, "personal")

    def search_memories(self, query: str, limit: int = 5):
        like = f"%{query}%"
        rows = self._exec(
            "SELECT key, content, layer FROM memory WHERE active = 1 AND "
            "(key LIKE ? OR content LIKE ?) ORDER BY updated DESC LIMIT ?",
            (like, like, limit)
        ).fetchall()
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════
# AGENT TOOLS (schema)
# ═══════════════════════════════════════════════════════════════════

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save something worth keeping long-term about Robert. "
                           "Use for projects, decisions, preferences, goals, people, "
                           "technical choices. Never save casual conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short unique slug, e.g. 'home_tower_os'"},
                    "content": {"type": "string", "description": "The fact to remember"},
                    "layer": {
                        "type": "string",
                        "enum": ["technical", "project", "personal", "business", "content"]
                    }
                },
                "required": ["key", "content", "layer"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_memory",
            "description": "Update an existing memory when information changes. "
                           "Always call this immediately when the user corrects you.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "content": {"type": "string", "description": "The new content"},
                    "reason": {"type": "string", "description": "What changed and why"}
                },
                "required": ["key", "content", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_memories",
            "description": "Search active memories before responding on a new topic. "
                           "Returns up to 5 matching memories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "name_thread",
            "description": "Name the current thread after your first response. "
                           "3-5 words, specific, never generic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                },
                "required": ["name"]
            }
        }
    },
]


# ═══════════════════════════════════════════════════════════════════
# PRIVYBOT CORE
# ═══════════════════════════════════════════════════════════════════

class PrivyBot:
    def __init__(self):
        self.name = os.getenv("PRIVY_NAME", "PrivyBot")
        self.default_model = os.getenv("DEFAULT_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        self.deep_model = os.getenv("DEEP_MODEL", "deepseek/deepseek-chat")
        self.claude_model = os.getenv("CLAUDE_MODEL", "anthropic/claude-sonnet-4")

        self.db = Database()
        self.tg = TelegramManager(handler=self)

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )

        self.current_thread: Optional[str] = None
        self._proc_lock = threading.Lock()

    # ── lifecycle ──
    def start(self):
        Logger.section(f"{self.name} ONLINE")
        self.tg.start()

        if self.db.memory_empty():
            Logger.warning(
                "[MEMORY] No memories found. Seed the database first: "
                "`uv run python seed.py` (edits live in context.yaml)."
            )

    def _ensure_thread(self):
        if not self.current_thread:
            self.current_thread = self.db.create_thread()
            Logger.info(f"📎 [THREAD] Created {self.current_thread[:8]}")

    # ── report layer (fire and forget) ──
    def report(self, event_type: str, **kwargs):
        try:
            if event_type == "save_memory":
                msg = f"📝 Noted [{kwargs.get('layer')}]: {kwargs.get('content')}"
            elif event_type == "update_memory":
                msg = f"✏️ Updated [{kwargs.get('key')}]: {kwargs.get('reason')}"
            elif event_type == "name_thread":
                msg = f"📎 Thread: {kwargs.get('name')}"
            elif event_type == "error":
                msg = f"🔴 Error: {kwargs.get('error')}"
            else:
                return
            threading.Thread(
                target=self.tg.send, args=(msg,), daemon=True
            ).start()
        except Exception as e:
            Logger.debug(f"[REPORT] {e}")

    # ── system prompt ──
    def _system_prompt(self) -> str:
        memories = self.db.active_memories()
        if memories:
            mem_text = "\n".join(
                f"- [{m['layer']}] {m['key']}: {m['content']}" for m in memories
            )
        else:
            mem_text = "(nothing yet)"

        base = (
            f"You are {self.name}, Robert Floyd Dugger's personal AI assistant "
            "running on his home tower in South Florida.\n\n"
            "What you know about Robert:\n"
            f"{mem_text}\n\n"
            "Memory rules — non-negotiable:\n"
            "1. Call name_thread() after first response in every new thread. 3-5 words. Specific.\n"
            "2. Call save_memory() when you learn something worth keeping. Announce it.\n"
            "3. Call update_memory() when information changes. Announce what changed.\n"
            "4. Call get_memories() when starting a new topic. Search before responding.\n"
            "5. Never save casual conversation. Save: projects, decisions, preferences, "
            "goals, people, technical choices.\n"
            "6. Always accept corrections immediately. User correction = update_memory() now."
        )
        return base

    # ── tool execution ──
    def _execute_tool(self, name: str, args: dict) -> str:
        try:
            if name == "save_memory":
                self.db.save_memory(args["key"], args["content"], args["layer"])
                self.report("save_memory", layer=args["layer"], content=args["content"])
                return f"saved memory '{args['key']}'"

            if name == "update_memory":
                self.db.update_memory(args["key"], args["content"])
                self.report("update_memory", key=args["key"], reason=args.get("reason", ""))
                return f"updated memory '{args['key']}'"

            if name == "get_memories":
                results = self.db.search_memories(args["query"])
                return json.dumps(results)

            if name == "name_thread":
                self._ensure_thread()
                self.db.set_thread_name(self.current_thread, args["name"])
                self.report("name_thread", name=args["name"])
                return f"thread named '{args['name']}'"

            return f"unknown tool: {name}"
        except Exception as e:
            self.report("error", error=str(e))
            return f"tool error: {e}"

    # ── credit-aware completion ──
    def _chat(self, model: str, messages: list):
        """Call OpenRouter. On 402 (insufficient credits) for a paid model,
        auto-retry once on the free DEFAULT_MODEL and notify via Telegram.
        Returns (response, model_actually_used)."""
        try:
            resp = self.client.chat.completions.create(
                model=model, messages=messages, tools=TOOLS,
            )
            return resp, model
        except Exception as e:
            is_402 = "402" in str(e) or "Insufficient credits" in str(e)
            if is_402 and model != self.default_model:
                Logger.warning(f"[MODEL] {model} hit 402; falling back to free model")
                self.report(
                    "error",
                    error=f"{model} needs OpenRouter credits — using free model instead.",
                )
                resp = self.client.chat.completions.create(
                    model=self.default_model, messages=messages, tools=TOOLS,
                )
                return resp, self.default_model
            raise

    # ── core agent loop ──
    def _run_agent(self, user_text: str, model: str) -> str:
        self._ensure_thread()
        tid = self.current_thread

        self.db.add_message(tid, "user", user_text)

        messages = [{"role": "system", "content": self._system_prompt()}]
        messages.extend(self.db.last_messages(tid, 10))

        active_model = model
        final_text = ""
        for _ in range(6):  # cap tool-call rounds
            resp, active_model = self._chat(active_model, messages)
            msg = resp.choices[0].message

            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    result = self._execute_tool(tc.function.name, args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                continue

            final_text = msg.content or ""
            break

        if final_text:
            self.db.add_message(tid, "assistant", final_text)
        return final_text

    # ── entrypoint from TelegramManager (runs in worker thread) ──
    def handle(self, text: str, command: Optional[str], args: str) -> str:
        with self._proc_lock:
            try:
                return self._handle(text, command, args)
            except Exception as e:
                Logger.error(f"[AGENT] {e}")
                self.report("error", error=str(e))
                return f"🔴 Error: {e}"

    def _handle(self, text: str, command: Optional[str], args: str) -> str:
        if command == "new":
            self.current_thread = self.db.create_thread(name="New conversation")
            self.report("name_thread", name="New conversation")
            return "📎 Started a new conversation. Memory is intact."

        if command == "memories":
            return self._format_memories()

        if command == "think":
            if not args:
                return "Usage: /think <message>"
            return self._run_agent(args, self.deep_model)

        if command == "claude":
            if not args:
                return "Usage: /claude <message>"
            return self._run_agent(args, self.claude_model)

        # Plain message → default model
        if not text:
            return ""
        return self._run_agent(text, self.default_model)

    def _format_memories(self) -> str:
        memories = self.db.active_memories()
        if not memories:
            return "🧠 No active memories yet."
        by_layer: dict = {}
        for m in memories:
            by_layer.setdefault(m["layer"], []).append(m)
        lines = ["🧠 Active Memories\n"]
        for layer in sorted(by_layer):
            lines.append(f"[{layer}]")
            for m in by_layer[layer]:
                lines.append(f"  • {m['key']}: {m['content']}")
            lines.append("")
        return "\n".join(lines).strip()


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    load_dotenv()

    missing = [
        k for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "OPENROUTER_API_KEY")
        if not os.getenv(k)
    ]
    if missing:
        Logger.critical(f"Missing env vars: {', '.join(missing)}. See .env.example.")
        sys.exit(1)

    bot = PrivyBot()
    bot.start()

    Logger.info("🛸 [SYSTEM] PrivyBot running. Ctrl+C to stop.")
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        Logger.info("🛸 [SYSTEM] Shutting down...")
        bot.tg.stop()


if __name__ == "__main__":
    main()
