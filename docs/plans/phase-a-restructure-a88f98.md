# Phase A: core/ → bot/ + infra/ Directory Restructure

Move core/ package into bot/ (Layers 2-4) and infra/ (Layer 5) with all import path updates.

## Branch and Safety
- Create branch: `restructure`
- Rollback: `git checkout dev` if blocked
- Success: 193/193 tests pass before and after deleting core/

## File Movement Map

**bot/ (Layers 2-4):**
- transport.py, router.py, agent.py, report.py, memory.py, scheduler.py, model_manager.py

**infra/ (Layer 5):**
- cache.py, rate_limits.py, polling.py
- db/ (all 17 submodules)

## Import Path Updates

**Internal (bot/ and infra/ files):**
- bot/* imports: `core.router` → `bot.router`, `core.agent` → `bot.agent`, `core.db` → `infra.db`
- infra/* imports: `core.db` → `infra.db`, `core.cache` → `infra.cache`, `core.rate_limits` → `infra.rate_limits`

**External files:**
- privybot.py: `core.transport` → `bot.transport`, `core.db` → `infra.db`
- tools/registry.py: `core.memory` → `bot.memory`
- tools/*.py: `core.db` → `infra.db`
- tools/api/*: `core.cache` → `infra.cache`, `core.rate_limits` → `infra.rate_limits`
- scripts/*: `core.db` → `infra.db`
- tests/*: `core.memory` → `bot.memory`, `core.db` → `infra.db`, `core.*` → `bot.*` or `infra.*`

## Verification Steps
1. Create new directories and files (old core/ still exists)
2. Update all import paths
3. Run `uv run python scripts/verify.py` → must be 193/193
4. Delete core/ directory
5. Run verify again → must be 193/193
6. Start bot with `uv run python privybot.py` → must start cleanly

## Stop Rules
- Phase A moves core/ only
- tools/ unchanged
- tools/api/ unchanged
- No tool function renames
- No registry.py content changes
- No test assertion changes
