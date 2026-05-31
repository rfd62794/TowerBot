# Self-Expansion Loop — Plan Docs to ADRs to Code

Two distinct questions with a convergence point at the end.

## 1. Plan Docs → ADRs and SDDs Conversion Process

Plans are inputs, not outputs. The conversion process:

```
Plan doc → design conversation → full ADR written → agent creates file → implementation directive
```

### Specific Conversions Required

**budget-tracking-mcp-expansion.md produces:**
- **ADR-034**: OpenRouter Budget Tracking
  - Context: autonomous tasks running, no cost visibility
  - Decision: hard cap ($0.10/day), track all calls, alert on paid
  - Consequences: paid calls blocked after cap, Telegram alerts
- **ADR-033 revision**: MCP HTTP+SSE+JWT replaces stdio-only design
  - Transport: HTTP/SSE (not stdio)
  - Host: localhost:8090
  - Public URL: Tailscale Funnel (https://[device].[tailnet].ts.net)
  - Auth: Bearer JWT, signed with MCP_TOKEN_SECRET
- **SDD_Budget_Tracking.md**: Implementation spec for budget tracking directive
- **SDD_MCP_HTTP_Server.md**: Implementation spec for MCP server directive

**autonomous-expansion.md produces:**
- **ADR-035**: Autonomous Task Architecture
  - Design decisions: persistent threads, shared memory, no retry, APScheduler
  - Task runner pattern: run_autonomous_task(), setup_autonomous_scheduler()
  - Action log: agent_actions table, overnight actions in briefing
- **SDD_Autonomous_Tasks.md**: Implementation spec for autonomous tasks

### Next Session Workflow

1. Write ADRs here (design conversation)
2. Agent creates ADR files
3. Agent creates SDD files
4. Implementation directives follow

**Plans never go directly to code** — they go through the ADR/SDD layer first. That's the methodology.

## 2. PrivyBot Accessing Its Own Repo

### Current State
- GitHub PAT already in `.env`
- `get_recent_commits` already uses it
- PrivyBot runs at `C:/Github/PrivyBot`

### New Tools Required

**Option A: GitHub API tools**
```python
"read_repo_file": read a specific file from the PrivyBot repo via GitHub API
"list_repo_contents": list a directory's contents
"search_repo_code": search codebase for a pattern
```

**Option B: Local file access (simpler, faster)**
```python
"read_local_file(path)": read local files directly, skip API entirely
```

### Autonomous Task: self_expansion_planner

```python
"self_expansion_planner": {
    "schedule_type": "cron",
    "hour": 3, "minute": 0,        # 3AM — after nightly_snapshot
    "enabled": False,               # start disabled, enable after testing
    "prompt": (
        "Read C:/Github/PrivyBot/docs/ROADMAP.md. "
        "Identify the next unimplemented item from the Build Sequence. "
        "Read the relevant SDD and ADRs for that area. "
        "Draft a directive in RFD methodology format: "
        "files to change, stop rule, success criteria. "
        "Save as memory 'Proposed directive: [name]'. "
        "Flag URGENT so Robert sees it in the morning briefing."
    ),
},
```

### Workflow
1. PrivyBot reads its own ROADMAP.md
2. Understands its own architecture via SDDs
3. Drafts the next build directive in RFD methodology format
4. Robert wakes up, reviews proposed directive, approves or adjusts
5. Hands to Windsurf for execution

## 3. The Convergence Point

This is what OpenAgent was supposed to be. OpenAgent reads a repo and generates strategic directives. You built it, published it, forgot about it.

**PrivyBot running OpenAgent on itself** is the closing of that loop — the tool you built to generate directives, applied to the system you're building, generating directives for the system to expand itself.

### OpenAgent Integration

OpenAgent is pip-installed and already on the machine. PrivyBot could call it as a subprocess:

```python
# In self_expansion_planner:
import subprocess
result = subprocess.run(
    ["openagent", "analyze", "--context", "next expansion phase"],
    capture_output=True,
    text=True
)
# Capture output, save to memory, flag for review
```

### Current Status
- openagent-directive: 60 downloads last month
- Baseline established: ~3 real downloads/week
- The plan is already built — it's called openagent-directive

### Not Tonight
This is not a task for tonight. But it's worth naming — the convergence point is clear.

## 4. Implementation Order

1. **Next session:** Write ADR-034, ADR-033 revision, ADR-035
2. **Next session:** Create SDD files
3. **Next session:** Implement budget tracking directive
4. **Later:** Implement MCP HTTP server directive
5. **Later:** Add read_local_file tool
6. **Later:** Implement self_expansion_planner (start disabled, test first)

## 5. Current State

- 4 autonomous tasks running overnight
- Tomorrow's 7AM briefing will show first overnight actions
- Plan docs saved: autonomous-expansion.md, budget-tracking-mcp-expansion.md, self-expansion-loop.md
- openagent-directive added to PrivyBot dependencies
- GitHub PAT already configured
- run_openagent tool implemented

## 6. OpenAgent Integration Blocker

**Bug 1 discovered:** openagent-directive 0.2.2 has a NameError in elaborator_agent.py:
```
NameError: name 'List' is not defined. Did you mean: 'list'?
```
**Status:** Fixed locally by adding `List` to imports.

**Bug 2 discovered:** DocumentationAgent is abstract and can't be instantiated:
```
TypeError: Can't instantiate abstract class DocumentationAgent without an implementation for abstract method 'execute'
```
**Status:** Not fixed. OpenAgent has multiple bugs preventing `openagent analyze` from running.

**Auth requirement:** OpenAgent uses OPENROUTER_API_KEY (from adk.json), not GOOGLE_API_KEY. PrivyBot already has this configured.

**Resolution options:**
1. Fix all bugs in C:\Github\OpenAgent and republish
2. Wait for upstream fixes
3. Defer OpenAgent integration until package is stable

**Status:** Blocked until OpenAgent package is fixed. The run_openagent tool implementation is complete but cannot be tested until the package works.
