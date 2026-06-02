# PrivyBot — Current State

## Phase
Phase 20c — Complete

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

- Phase 20b: Approval Step + Telegram Reply Router
  - infra/chain/approval.py: Approval listener CRUD + message building
  - infra/chain/steps.py: Real approval_wait handler (creates listener, calls send_fn)
  - bot/approval_router.py: Callback parser + handler
  - bot/transport.py: handle_callback_query async handler
  - privybot.py: CallbackQueryHandler registration
  - 18 new tests in test_approval.py
  - Test floor: 417 passed, 0 failed

- Phase 20c: Observer + Digest + First Template + Production Wiring
  - templates/canonical/hourly_fact.yaml: First canonical template (3 steps)
  - infra/chain/template_loader.py: YAML loading + validation
  - infra/chain/observer.py: Pattern observation logic
  - bot/autonomous.py: Observer job (30min) + weekly digest (Sunday 08:00)
  - bot/approval_router.py: resume_chain_fn wired to real ChainRunner
  - 20 new tests in test_phase20c.py
  - Test floor: 437 passed, 0 failed

## Next
Phase 21: Promotion pipeline, n8n integration, model roles config

---

## Admin Tools (Post-Phase 20c)
- tools/meta/admin.py: get_logs() and run_diagnostic() added
- tools/registry.py: Both tools registered
- config/routes.yaml: Both tools added to tasks route
- tests/test_admin_tools.py: 8 tests
- Test floor: 445 passed, 0 failed
