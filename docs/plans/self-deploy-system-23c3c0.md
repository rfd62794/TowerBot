# Self-Deploy System

Implement `/deploy` command with inline git pull + verify + self-restart, and `launch.py` crash-revert watchdog for safe Tower deployments.

## Current State
- `scripts/deploy.py` exists but calls NSSM directly (not self-restart)
- `bot/router.py` has `handle_deploy()` that calls deploy.py as subprocess
- No crash-revert mechanism — bad deploys require manual SSH fix

## Design

### `/deploy` Command (bot/router.py)
Replace subprocess call to deploy.py with inline logic:
1. Guard: only TELEGRAM_CHAT_ID can trigger (already in .env)
2. `git rev-parse HEAD` → save to `.last_good_commit`
3. `git fetch` → check if behind → if current, reply "Nothing to deploy"
4. `git pull`
5. `subprocess verify.py` → parse "N/N" from output
6. If fail: `git checkout saved hash` → reply "❌ Tests failed: N/M — reverted"
7. If pass: reply "✅ N/N — restarting..." → `.deploy_restart.touch()` → `sys.exit(0)`

### `launch.py` Watchdog (new file, repo root)
- Reads TELEGRAM_TOKEN + TELEGRAM_CHAT_ID from .env for revert alerts
- Tracks `last_deploy_time` (float) and `last_good_commit` (str)
- Before subprocess start: reads `.deploy_restart` → sets `was_deploy=True`, deletes flag
- Subprocess: `uv run python privybot.py` (uses venv)
- On subprocess exit:
  - `uptime = time.time() - start_time`
  - If `was_deploy` and `uptime < 60`: bad deploy → `git checkout last_good_commit` → send Telegram alert → restart
  - Otherwise: just restart
- Loops forever

### Tests (tests/test_deploy.py)
- `test_deploy_skips_when_nothing_to_pull`
- `test_deploy_reverts_on_test_failure`
- `test_deploy_writes_restart_flag_on_success`
- `test_watchdog_reverts_on_fast_crash_after_deploy`
- `test_watchdog_does_not_revert_on_slow_crash`
- `test_watchdog_skips_revert_when_no_deploy_flag`

## Files
- `launch.py` (new, repo root)
- `bot/router.py` (replace handle_deploy with inline logic)
- `tests/test_deploy.py` (new, 6 tests)

## Stop Rule
- launch.py — new file only
- bot/router.py — handle_deploy function only
- tests/test_deploy.py — 6 tests
- No changes to privybot.py, agent.py, scheduler.py
- scripts/deploy.py — becomes dead code, log as cleanup backlog

## Success
- 324 + 6 = 330/330 pass
- Manual test: run launch.py in terminal, confirm privybot.py starts
- /deploy with no new commits → "Nothing to deploy"
