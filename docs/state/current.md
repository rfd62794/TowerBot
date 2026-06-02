# PrivyBot — Current State

## Phase
Phase 24 — Complete

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

- Phase 21: Model Roles + Pydantic + Reasoning
  - infra/chain/schemas.py: Pydantic payload schemas (BasePayload, TextDraftPayload, DataStatsPayload, etc.)
  - infra/db/payloads.py: Pydantic validation on create_payload with fallback to raw dict
  - infra/db/budget_tracking.py: Added get_warning_sent_today() and mark_warning_sent()
  - infra/db/budget_tracking.py: Made record_cost daily_cap_usd optional with registry fallback
  - config/model_registry.yaml: Model capability registry with 8 models, 8 roles, budget caps
  - infra/model_router.py: Role-based model router with budget awareness and spend tracking
  - infra/chain/steps.py: Added StepLoopBack exception, handle_agent_step(), handle_loop_back()
  - infra/chain/runner.py: Handle StepLoopBack with anchor step reset, route llm_call through model router
  - bot/router.py: Added budget spend to /status output
  - 24 new tests in test_phase21.py
  - Test floor: 497 passed, 0 failed

- Phase 22: Director Tools — Full Operational Access
  - tools/meta/director.py: 13 new tools for Claude (chains, templates, memories, DB inspection)
  - Chain tools: get_chains, get_chain, get_chain_payload, start_chain, cancel_chain, resume_chain
  - Template tools: list_templates, get_template, write_template, delete_experimental_template
  - Memory tools: list_memories, delete_memory
  - Pattern tools: get_promotion_candidates
  - DB inspection: query_db (SELECT-only)
  - Hard boundary: write_template and delete_experimental_template cannot touch canonical/
  - All 13 tools registered in TOOL_REGISTRY and exposed via MCP
  - 22 new tests in test_director_tools.py
  - Test floor: 519 passed, 0 failed

- Phase 23: Tool Discovery + Dynamic Registration
  - infra/db/schema.py: Added experimental_tools table for dynamic tool registry
  - tools/meta/tool_registry.py: 4 new tools (a2a_search, register_tool_from_spec, list_experimental_tools, promote_tool)
  - a2a_search: Search a2asearch.com index for MCP tools and skills with fallback URL
  - register_tool_from_spec: Fetch OpenAPI spec, generate tool definitions, register to experimental_tools table
  - list_experimental_tools: List dynamically registered tools with status filter
  - promote_tool: Promote experimental tool to promoted status (explicit call only, no auto-promotion)
  - All 4 tools registered in TOOL_REGISTRY and auto-exposed via MCP
  - 18 new tests in test_tool_registry.py
  - Test floor: 537 passed, 0 failed

- Phase 24: Model Router Wiring + Tool Index
  - config/task_types.yaml: Added model_role field to all 5 TaskTypes (monitor, reporter, creator, planner, chat)
  - Model role mappings: monitor→fast_intent (Groq), reporter→long_context (Gemini Flash), creator→long_context (Gemini Flash), planner→reasoning (DeepSeek), chat→chat (Gemini Flash)
  - config/model_registry.yaml: Updated groq_llama_3_1_70b and gemini_flash to use direct providers (groq, google) instead of openrouter
  - bot/model_helpers.py: Added provider-specific call functions (call_groq, call_gemini, call_openrouter) and get_call_fn(provider)
  - bot/autonomous.py: Wired model_router into run_autonomous_task() and process_delegation_queue()
  - Autonomous tasks now route through model_router based on task_type's model_role
  - infra/model_router.py: Updated route() to use get_call_fn(provider) for provider-specific API calls
  - tools/meta/tool_index.py: 3 new tools (search_tools, list_all_tools, get_tool_info)
  - search_tools: Fast fuzzy search of all registered tools by name and description
  - list_all_tools: List all tools with optional prefix filter
  - get_tool_info: Get full information about a specific tool by exact name
  - All 3 tool index tools registered in TOOL_REGISTRY and auto-exposed via MCP
  - config/routes.yaml: Added 3 tool index tools to system route with trigger phrases
  - 11 new tests in test_model_wiring.py
  - Test floor: 548 passed, 0 failed

## Next
Phase 25: TBD

---

## Admin Tools (Post-Phase 20c)
- tools/meta/admin.py: get_logs() and run_diagnostic() added
- tools/registry.py: Both tools registered
- config/routes.yaml: Both tools added to tasks route
- tests/test_admin_tools.py: 8 tests
- Test floor: 445 passed, 0 failed
