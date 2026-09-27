# Direction: PrivyBot

## Purpose

PrivyBot is Robert Floyd Dugger's personal AI assistant: a Telegram bot that
routes messages to OpenRouter (free models first, paid capped), holds
conversation context and memory in SQLite, and runs autonomous background
work. It lives on Robert's own hardware and is designed to cost nothing to
run. (README.md, docs/VISION.md)

## Current state

- Deployed on the Tower as an NSSM Windows service; `/deploy` on Telegram
  triggers a self-update. (README.md, docs/TOWER_DEPLOY.md, scripts/deploy.py)
- docs/state/current.md records Phase 33 (RALPH, the persistent overseer)
  complete with a stated test floor of 604/0.
- verify_result.txt records "586 passed, 18 failed — Deploy blocked", and that
  file predates the latest commits, so the true floor is unverified.
- bot/ralph.py and bot/scheduler.py are committed as UTF-16LE (commit f9334f4
  "Restore RALPH and scheduler from maintenance mode"); Python cannot import
  them (SyntaxError), which fails the ralph, scheduler, and core heartbeat
  tests.
- pytest collects 671 tests, but the documented gate is scripts/verify.py,
  which calls init_db() before loading test files — bare `uv run pytest`
  fails DB tests that rely on that initialisation.
- Semantic memory (infra/memory_manager.py, Chroma + Ollama) and a
  dual-transport MCP server (infra/mcp/) already exist — the Phase 15 section
  of docs/ROADMAP.md is stale relative to docs/state/current.md.
- ~55 tools registered: 46 per docs/ROADMAP.md plus 9 browser tools added in
  Phase 32a (docs/state/current.md).

## Next steps

Ordered per the yaml roadmap block in docs/ROADMAP.md (drafted 2026-09-22):

1. M1 — restore a green `uv run python scripts/verify.py`: re-encode the two
   UTF-16 source files, triage the recorded 18 failures, fix what remains.
2. M2 — finish Phase 12 DB hardening: schema_migrations versioning, daily
   backup, weekly vacuum, connection pooling / explicit transactions /
   health checks. (docs/ROADMAP.md Phase 12 "Remaining";
   docs/plans/outstanding-work.md)
3. M3 — Phase 13 logging infrastructure: structured JSON logs, trace_id via
   async contextvars, rotation, performance metrics, error aggregation.
   (docs/ROADMAP.md Phase 13)
4. M4 — housekeeping: the remaining Phase 11 type hints on API and tool
   functions, and resync the ROADMAP phase table plus
   docs/plans/outstanding-work.md with docs/state/current.md.

## Definition of done

- `uv run python scripts/verify.py` exits 0 and writes "Deploy safe." to
  verify_result.txt. (README.md "Development Workflow", scripts/verify.py)
- Robert merges work to main and deploys to Tower; agents do not merge or
  deploy. (README.md: "main — Tower production, never commit directly")
- docs/state/current.md is updated when a phase or step lands — the
  convention visible in every entry there.

## Do not

- Do not commit directly to main — it is Tower production. (README.md)
- Do not enable RALPH by default — RALPH_ENABLED is opt-in via env var.
  (commit 36e09d1)
- Do not route generative inference to local Ollama — Ollama is for
  embeddings only; generative calls go to cloud. (commit b119dc4)
- Do not let the agent update goals autonomously — it suggests via
  suggest_goal_progress only. (docs/ROADMAP.md Phase 6 "Key Decisions")
- Do not commit secrets: .env, OAuth tokens, client secrets, and
  config/playwright_profiles/ are gitignored. (.gitignore, commits 2f975fc,
  772c8bc)
- Do not add paid dependencies — the project targets $0/month on free
  models and free APIs. (docs/VISION.md "Why Free Models?")

## Sources of truth

- README.md — setup, dev workflow, MCP configuration, deploy
- docs/ARCHITECTURE.md — layered architecture and import rules
- docs/VISION.md — philosophy and long-term direction
- docs/ROADMAP.md — phase plan and the yaml roadmap block
- docs/state/current.md — most recent completed-phase state
- docs/plans/outstanding-work.md — declared-but-unbuilt items (partially stale)
- docs/adr/ — architecture decision records (ADR-001 through ADR-040)
- config/tasks.yaml — autonomous task schedule
- scripts/verify.py + verify_result.txt — the deploy gate and last recorded floor

---

## Direction questionnaire (AI-drafted, unconfirmed - 2026-09-27)

The six answers below are Claude's best guess from this file's own evidence
(prose above), README/AGENTS/ROADMAP/state docs, git log and Portfolio's
projects.yaml - not something Robert has answered yet. `answered` stays
empty until he corrects or confirms them (`agentflow direction ask PrivyBot`,
or `direction PrivyBot = <answer>` in chat, one field at a time).

| Field | Confidence / note |
|---|---|
| `purpose` | HIGH |
| `done_when` | HIGH |
| `do_not` | HIGH |
| `audience` | HIGH |
| `hours_per_week` | GUESS - infra tier, ongoing maintenance, no stated budget. |
| `stakes` | GUESS - private single-user bot, revertible via redeploy from git; but it runs live on Tower production and is Robert's daily assistant, so a case could be made for medium instead of low. |

```yaml direction
version: 1
answered: ""
purpose: "Robert's personal Telegram AI assistant on the Tower: routes messages to OpenRouter (free models first), holds conversation context and memory in SQLite, and runs autonomous background work (RALPH) - designed to cost nothing to run."
done_when:
  - "`uv run python scripts/verify.py` exits 0 and writes \"Deploy safe.\" (the deploy gate is currently blocked: verify_result.txt records 18 failures, and two source files are stuck as unparseable UTF-16)."
  - "Phase 12 DB hardening (migrations, backups, connection pooling) and Phase 13 logging (structured JSON, trace_id) land."
  - "docs/ROADMAP.md's phase table and docs/plans/outstanding-work.md resync with docs/state/current.md, which is ahead of both."
do_not:
  - "Never commit directly to main - it is Tower production."
  - "Never enable RALPH by default - it is opt-in only via env var."
  - "Never route generative inference to local Ollama - cloud only; Ollama is embeddings-only."
  - "Never add paid dependencies - the project targets $0/month on free models and free APIs."
audience: me
hours_per_week: "<1"
stakes: low
```
