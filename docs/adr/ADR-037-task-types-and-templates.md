# ADR-037: TaskTypes and Templates for Autonomous Tasks

## Status
Superseded by ADR-037.md

## Context
Autonomous tasks are currently bespoke — each task is a hand-written prompt with implicit knowledge about iteration depth, persona, and behavior. Adding a new task requires writing a prompt from scratch and knowing the right configuration. This knowledge is implicit and not reusable.

Problems:
- Iteration limits are hardcoded per task, not configurable by task type
- Persona and behavior patterns are repeated across similar tasks
- Adding a new monitor or reporter task requires prompt writing from scratch
- Reactive signal emission is ad-hoc, not defined by task type
- The system is hard to reason about as bespoke tasks accumulate

## Decision
Introduce a three-layer system: TaskType (behavior profile) → Template (prompt structure) → Task instance (schedule + params).

### TaskTypes
Behavior profiles that define iteration limits, persona, and signal emission:

```yaml
monitor:
  max_iterations: 5
  persona: "Monitor for signals. Be brief. Report factually."
  emit_signals: true
  fallback_on_empty: true

planner:
  max_iterations: 25
  persona: "Think step by step. Use tools systematically."
  save_to_memory: true
  stage_output: true

reporter:
  max_iterations: 10
  persona: "Summarize clearly. Pull data before drawing conclusions."
  urgent_on: [spike, mention, milestone, urgent]

creator:
  max_iterations: 15
  persona: "You are PrivyBot's content creator."
  outputs: [blog_draft, memory]
```

### Templates
Reusable prompt structures with parameter placeholders:

```yaml
reddit_monitor:
  type: monitor
  prompt: |
    Search {subreddits} for {keywords} in the last {hours}h.
    If found: save to memory, mark URGENT.
    Report what you found.

metric_snapshot:
  type: reporter
  prompt: |
    Pull {data_sources} metrics. Compare to yesterday's memory.
    Save as memory '{label} {date}'. Note any significant change.

content_advance:
  type: creator
  prompt: |
    Call advance_post_pipeline() to advance the most in-progress
    blog post by exactly one stage. Report what stage was completed.

self_expand:
  type: planner
  prompt: |
    Call read_current_state(), find_opportunities(focus='{focus}'),
    generate_directive(). Save directive as memory 'Proposed directive: [name]'.
    Mark URGENT.
```

### Task Instances
Schedule and filled-in parameters only:

```yaml
itch_reddit_check:
  template: reddit_monitor
  schedule: {type: interval, minutes: 30}
  params: {keywords: [VoidDrift], subreddits: [r/incremental_games, r/gamedev], hours: 24}

nightly_snapshot:
  template: metric_snapshot
  schedule: {type: cron, hour: 23, minute: 30}
  params: {data_sources: [youtube, itch], label: "Daily metrics"}

self_expansion_planner:
  template: self_expand
  schedule: {type: cron, hour: 7}
  params: {focus: "next phase"}
```

## Implementation
1. Create `config/task_types.yaml` with four TaskTypes (monitor, planner, reporter, creator)
2. Create `config/task_templates.yaml` with templates for existing tasks
3. Refactor `run_autonomous_task()` to:
   - Load TaskType by template.type
   - Inject persona from TaskType
   - Use max_iterations from TaskType
   - Handle emit_signals, save_to_memory, urgent_on flags
4. Migrate existing six tasks to template instances
5. Add iteration limit to .env as temporary bridge (migrates to task_types.yaml after)

## Consequences
**Positive:**
- Iteration limits configurable per task type, not per task
- Persona and behavior patterns reusable
- Adding new tasks is three lines (template, schedule, params)
- Reactive signal emission defined by TaskType
- System easier to reason about as tasks grow

**Negative:**
- Migration effort for existing six tasks
- Additional YAML files to maintain
- TaskType definitions need tuning (iteration limits, personas)

**Risks:**
- TaskType definitions may need iteration as patterns emerge
- Template parameter names must be consistent
- Migration may expose implicit assumptions in existing prompts

## Alternatives Considered
- Keep bespoke tasks with per-task iteration limits — rejected: doesn't solve reusability
- Use code-based task classes instead of YAML — rejected: YAML is more declarative and easier to edit
- Add iteration limits only, no templates — rejected: doesn't solve persona and reusability problems

## Notes
- Stop rule on new bespoke tasks until this system is in place
- Iteration limit fix tonight is a temporary one-liner in .env
- This is the architecture Phase 16 should have been built on
