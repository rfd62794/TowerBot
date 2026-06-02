# PrivyBot — Current State

## Phase
Phase 20a — Complete

## Completed
- Phase 19: Chain System Foundation (ADR-037 + Schema)
  - ADR-037.md: Six primitive architecture locked
  - 5 new SQLite tables: chains, chain_steps, chain_payloads, pattern_candidates, approval_listeners
  - infra/db/chains.py: Chain and step CRUD
  - infra/db/payloads.py: Payload CRUD with JSON serialization
  - templates/canonical/ and templates/experimental/ directories created
  - 15 new tests in test_chain_schema.py
  - Test floor: 379 passed, 0 failed

- Phase 20a: Chain Runner + Step Execution
  - infra/chain/runner.py: ChainRunner with injected dependencies
  - infra/chain/steps.py: 6 step handlers + StepError + StepSkipped
  - infra/chain/__init__.py: package init
  - 20 new tests in test_chain_runner.py
  - Test floor: 399 passed, 0 failed

## Next
Phase 20b: approval_wait step type, Telegram reply router
