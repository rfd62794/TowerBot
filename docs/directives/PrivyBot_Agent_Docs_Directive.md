# PrivyBot: agent documentation hardening (AGENTS.md + direction state)

## 1. Why this exists

This repo is dispatch-eligible — the AgentFlow queue can send a Devin run here — but it
has no `AGENTS.md`, so a dispatched agent starts with no map of the layout, no verified
test command, and no record of where the project is headed. On 2026-09-21 Robert set the
direction: every open project gets stronger documentation so agents can interpret the
general direction and work as they see fit. This is that pass for PrivyBot.

## 2. Scope

Work in your dispatch worktree on this directive's branch. Never touch `main`.

Create:
- `AGENTS.md` at the repo root — the file every agent reads first. Contents:
  - one line on what the project is and who it serves;
  - the layout map (which directories hold what — derived from the real tree, not guessed);
  - the build/test/run commands, each **verified by actually running it** before you
    write it down (a wrong command in AGENTS.md is worse than none);
  - conventions visible in the existing code (test style, commit style, naming);
  - boundaries: what an agent must not touch, what lives outside the repo, no secrets.
- `docs/state/current.md` (create `docs/state/` if missing; if a state file already
  exists, refresh it instead of duplicating) — where the project stands today and the
  honest next actions, so the next agent inherits direction, not just structure.

If the repo already has a README or docs that cover some of this, AGENTS.md points at
them rather than duplicating.

## 3. Rules

- Docs only — no code changes, no dependency changes, no config changes.
- Every command written into AGENTS.md must have been run by you first; say in the
  report what each returned.
- Read enough real code/docs to be accurate — a plausible-but-wrong map is a defect.
- No secrets, nothing personal, nothing from the work side that doesn't belong in a
  generic doc.
- Commit on your directive branch and push; do not commit to `main`.

## 4. Completion criteria

- [ ] `AGENTS.md` exists, is accurate, and every command in it was verified live.
- [ ] `docs/state/current.md` (or the repo's existing state file) names current status
      and next actions.
- [ ] Report lists each verified command with its real output summary.

## 5. Next phase (self-progression)

The queue is self-refilling: if writing the docs surfaced a clear, well-scoped follow-up
(a broken test, a stale doc claiming false things, an obvious improvement), draft it as
a new directive in `docs/directives/` with status `Draft` per
`AgentFlow/docs/templates/directive.template.md`, and name it in the report. If nothing
clear surfaced, say so — do not invent work.

## 6. Report

Commands verified + their results, files written, commit hash(es), and any successor
directive drafted.

<!-- queue:start -->
## Queue

| Field | Value |
|---|---|
| Status | Queued |
| Assigned to | devin |
| Branch | - |
| Base branch | - |

**Status log**
- 2026-09-21 · devin · none → Queued — AgentDocs wave 0: docs hardening before improvement
  phases (Robert 2026-09-21 "go wide ... stronger documentation ... agents interpret as
  they see fit"). Batch of 10, one per repo missing AGENTS.md.
<!-- queue:end -->
