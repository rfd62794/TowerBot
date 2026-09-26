# AGENTS.md — PrivyBot

Robert Floyd Dugger's personal AI assistant: a Telegram bot that routes messages to
OpenRouter, holds conversation context and memory in SQLite, and runs autonomous
scheduled work. It lives on Robert's own hardware (the "Tower") as an NSSM Windows
service and is designed to cost $0/month. Single-user, not a product.

## Read first

- `README.md` — setup, `.env` keys, bot commands, MCP server config, deploy workflow
- `docs/DIRECTION.md` — purpose, current state, next steps, "do not" list. Most
  current orientation doc; start here.
- `docs/ARCHITECTURE.md` — layered architecture and strict import rules
- `docs/adr/` — ADR-001 through ADR-040; check before changing a design decision
- `docs/ROADMAP.md` — yaml roadmap block (M1–M4) and phase table
- `docs/state/current.md` — phase log, newest first; update it when work lands
- `docs/TOOLS.md` — how to add a tool (`TOOL_REGISTRY` pattern)
- `docs/TOWER_DEPLOY.md` — NSSM deployment on Tower
- `SOUL.md` — owner's working preferences (test fails = non-negotiable, prevent creep)

## Layout (from the real tree)

| Path | Holds |
|---|---|
| `privybot.py` | Entry point: env validation, `init_db()`, PTB app, APScheduler, RALPH startup |
| `launch.py` | Watchdog wrapper: restarts `privybot.py`, auto-reverts a deploy that crashes <60s |
| `bot/` | Bot core: `transport.py` (L0 Telegram), `router.py`/`router_ai.py` (L1), `agent.py` (L2 OpenRouter + tool exec), `report.py` (L3), `memory.py` (L4 memory tools), `scheduler.py`, `autonomous.py`, `ralph.py` (persistent overseer), `model_manager.py`, `formatter.py`, `approval_router.py`, `task_runner.py`, `prompts/` |
| `infra/` | Infrastructure: `db/` (SQLite schema, per-table CRUD, `manager.py` DBManager), `cache.py` (L7), `rate_limits.py` (L7b), `polling.py` (L7c), `memory_manager.py` (L7d semantic memory: Chroma + Ollama), `mcp/` (MCP server, dual transport), `chain/` (approval chains), `model_router.py`, `prompts.py`, `utils.py` |
| `api/` | External API clients (L8) by source: `google/`, `steam/`, `weather/`, `web/`, `github/`, `local/` (Ollama), `mcp/`. `_base.py` = `BaseAPIHandler` cached-call pattern |
| `tools/` | Tool logic (L6) by domain: `productivity/`, `content/` (YouTube), `games/`, `search/`, `browser/` (Playwright), `communication/`, `repo/`, `meta/`, `system/`. `registry.py` = `TOOL_REGISTRY`, the single source of truth |
| `config/` | YAML config: `tasks.yaml` (autonomous schedule), `routes.yaml`, `providers.yaml`, `model_registry.yaml`, `timeouts.yaml`, `goals.yaml`, `plans.yaml`, templates |
| `templates/` | Task prompt templates — `canonical/` (base_prompts, deep_dive, ralph_overseer, …), `experimental/` |
| `tests/` | pytest suite (~677 tests). `_harness.py` (@test decorator + `run_all()`) shared with `verify.py`; `_setup.py` and `conftest.py` call `init_db()` |
| `scripts/` | Ops: `verify.py` (deploy gate), `deploy.py`, `seed.py`, OAuth helpers, cleanup/migration scripts |
| `docs/` | All documentation: `adr/`, `sdd/`, `plans/`, `state/`, `directives/` |
| `verify_result.txt` | Last recorded deploy-gate result (currently stale: "586 passed, 18 failed — Deploy blocked") |

## Commands

Python is `uv`-managed (pin `>=3.12,<3.13` — ADR-009: Python 3.14 has a TLS bug).
`uv run` auto-syncs `.venv` from `uv.lock` on first use; do not create venvs or
install packages by hand. `requirements.txt` exists for non-uv environments.

Verified in a clean worktree on 2026-09-24 (Python 3.12.12, 145 packages synced):

```bash
uv run python --version          # -> Python 3.12.12
uv run pytest tests/test_transport.py -q   # -> 6 passed (needs TELEGRAM_CHAT_ID set)
uv run pytest                    # full suite — see caveat below
```

**Test caveat — `uv run pytest` needs `TELEGRAM_CHAT_ID`.**
`bot/transport.py` calls `int(os.getenv("TELEGRAM_CHAT_ID"))` at module import, so
collection aborts in a worktree with no `.env`. Set a dummy value first:

```powershell
$env:TELEGRAM_CHAT_ID = "1"     # PowerShell
uv run pytest
```

In a clean worktree (no `.env`, no OAuth tokens) the suite reports ~521 passed /
156 failed. The failures group into: UTF-16-encoded `bot/ralph.py` +
`bot/scheduler.py` (SyntaxError on import — roadmap step M1.1), missing OAuth/API
credentials (gmail, calendar, tasks, YouTube, Steam, WordPress, `MCP_JWT_SECRET`),
and DB init-ordering `AttributeError: 'NoneType'` in the `test_db`/`test_polling`/
`test_rate_limits` files. A green run requires the real `.env` and tokens.

**Deploy gate (not runnable in a bare worktree):** `uv run python scripts/verify.py`
is the documented gate (README, ROADMAP). It calls `init_db()`, executes each test
file's `run_all()`, writes `verify_result.txt`, and exits 0 = "Deploy safe." It
needs the full `.env` and OAuth tokens; it was not executed in this worktree.

**Running the bot:** `uv run python privybot.py` needs the real `.env`
(`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OPENROUTER_API_KEY`) and talks to live
Telegram — never start it from a worktree. The MCP server
(`uv run python infra/mcp/server.py --transport stdio|sse`) is likewise a live
service; see README § "MCP Server" for config.

## Conventions

- **Layers:** strict one-way imports, higher layer → lower only; no circulars.
  Full rules and per-layer contracts in `docs/ARCHITECTURE.md`.
- **New tools:** implement in `tools/<domain>/`, register `fn` + JSON schema in
  `tools/registry.py` `TOOL_REGISTRY`; `agent._execute()` dispatches automatically.
  Return dicts (`{"status": "success"|"error", ...}` / BaseTool `ok` shape). Guide:
  `docs/TOOLS.md`.
- **Tests:** dual-mode files — `test_*` functions collected by pytest, plus a
  `run_all()`/`@test` harness entry for `scripts/verify.py`. New DB-touching tests
  should use the `test_db` fixture (root `conftest.py`) for `:memory:` isolation.
- **Commits:** short imperative, conventional prefixes (`fix:`, `chore(scope):`,
  `docs:`); queue bookkeeping commits are prefixed `Queue:`.
- **State doc:** when a phase/step lands, prepend a dated entry to
  `docs/state/current.md` (newest first) — that is the established convention.
- **File encoding:** save source as UTF-8. `bot/ralph.py` and `bot/scheduler.py`
  were committed as UTF-16LE (PowerShell redirect artifact) and currently fail to
  import — do not repeat.

## Boundaries

- `main` is Tower production — never commit, merge, or push to it. Robert merges
  and deploys; `/deploy` on Telegram triggers self-update via `launch.py`.
- No secrets in the repo: `.env`, OAuth tokens, `client_secret*.json`,
  `config/playwright_profiles/`, `*storage_state*.json` are gitignored — keep it so.
- `privy.db` (and `privy_chroma_db/`) is live data — never commit or delete it.
- `RALPH_ENABLED` stays opt-in via env var — do not enable by default.
- Ollama is for embeddings/classification only; generative inference goes to cloud
  (OpenRouter). Do not route generative calls to local models.
- The agent suggests goal progress (`suggest_goal_progress`); it never updates
  goals autonomously.
- No paid dependencies or paid APIs — the project targets $0/month (VISION.md).
