# PrivyBot: make `uv run pytest` usable in a clean checkout

## 1. Why this exists

Drafted during the agent-docs pass (2026-09-24). In a fresh worktree with no
`.env` and no OAuth tokens, `uv run pytest` is broken in two ways that have
nothing to do with missing credentials:

1. **Collection aborts outright.** `bot/transport.py:26` runs
   `int(os.getenv("TELEGRAM_CHAT_ID"))` at module import, so
   `tests/test_transport.py` raises `TypeError` during collection and pytest
   exits 2 without running anything.
2. **DB tests lose their connection.** With `TELEGRAM_CHAT_ID` set, the suite
   runs but ~50 tests fail with `AttributeError: 'NoneType'` on `schema._conn`
   (test_db, test_polling, test_rate_limits). `scripts/verify.py` calls
   `init_db()` before loading test files; bare pytest depends on conftest/fixture
   ordering, and the root `conftest.py` `test_db` fixture resets
   `schema._conn = None` on teardown — tests that imported the module-level
   `init_db()` connection then hit `None`.

A suite that only runs green inside the production checkout is a trap for every
dispatched agent: they cannot tell env-dependent failures from real regressions.
Measured baseline (clean worktree, `TELEGRAM_CHAT_ID=1`): 521 passed / 156
failed of 677 collected.

## 2. Scope

Work on this directive's branch. Never touch `main`.

- `bot/transport.py` — make import not require `TELEGRAM_CHAT_ID` (lazy read or
  guarded default; keep runtime gating behavior identical).
- `tests/conftest.py` and/or `infra/db/schema.py` — make the DB connection
  survive under bare pytest: either `init_db()` re-initializes after the
  `test_db` fixture resets `_conn`, or the fixture restores the prior connection.
- No other source changes. Do not weaken test assertions to make them pass.
- Credential-dependent failures (gmail, YouTube, Steam, WordPress, MCP JWT) are
  out of scope — they need secrets a worktree does not have.

## 3. Rules

- Verify with `TELEGRAM_CHAT_ID` unset AND set: `uv run pytest` must collect and
  run in both cases; the 'NoneType' failures must be gone.
- Re-run the full suite and record the new floor in `docs/state/current.md`.
- Do not fix the UTF-16 files here — that is roadmap step M1.1, tracked
  separately.
- Commit on the directive branch; do not commit to `main`.

## 4. Completion criteria

- [ ] `uv run pytest` collects and runs with no `.env` present.
- [ ] No `AttributeError: 'NoneType'` failures from `schema._conn` in the run.
- [ ] `docs/state/current.md` records the new clean-worktree floor.

## 5. Report

Commands verified + results, files changed, commit hash(es), remaining failure
groups after the fix.

<!-- queue:start -->
## Queue

| Field | Value |
|---|---|
| Status | Draft |
| Assigned to | devin |
| Branch | - |
| Base branch | - |
| Base commit | 517018899bd488ad6cfe2713dcfd560893f08b97 |

**Status log**
- 2026-09-24 · devin · none → Draft — surfaced by PrivyBot_Agent_Docs_Directive run
<!-- queue:end -->
