# Hard Rules for Cascade Agent

## Branch Protection

**CRITICAL: Never push to main. NEVER. Not even with user approval.**

### Workflow
1. All work happens on `dev` branch
2. Changes must be proven on `dev` (tests passing, spot checks verified)
3. Never merge `dev` to `main`
4. Never push `main` to origin
5. Never switch to `main` branch

### Forbidden Actions
- Never run `git push origin main` — EVER
- Never merge `dev` to `main` — EVER
- Never switch to `main` branch — EVER
- Never push to origin/main — EVER

### Current Branch
Always work on `dev` branch. Verify with:
```bash
git branch
# Should show: * dev
```

### Pushing to dev
Push to dev is allowed after work is proven:
```bash
git push origin dev
```

## Test Requirements

Before requesting user approval for main merge:
- All tests must pass: `uv run python scripts/verify.py`
- Current test floor: 576/0/0 (check docs/state/current.md for certified floor)
- Spot checks must verify key functionality

## Test Runner: verify.py vs pytest

**verify.py is the authoritative test suite runner.**

- `scripts/verify.py` runs all test files in a specific order (see TEST_FILES list)
- This is the full test suite that determines deployment safety
- Always use verify.py to check the certified test floor

- `pytest` can be used for quick checks on individual test files
- Example: `uv run pytest tests/test_admin_tools.py`
- pytest does NOT run the full suite and is not authoritative for deployment

**Never assume pytest results represent the full test floor.**

## Deployment Safety

Changes are only "deploy safe" when:
- All tests pass
- Spot checks verified
- User explicitly approves main merge

## ADR-038 Stop Rule (June 2026)

Do NOT write new code that reads from or writes to the `tasks` or `personal_tasks`
tables. These tables are deprecated per ADR-038 and will be dropped in Phase 2.

If a task requires storing or retrieving user tasks:
- Use Google Tasks API tools (`list_google_tasks`, `create_google_task`, etc.)

If a task requires storing autonomous bot work:
- Use the `task_queue` table (conceptually: job_queue)

If you encounter existing code that queries these tables, add a deprecation
warning per ADR-038 Phase 1 directive — do not silently extend or modify the query.
