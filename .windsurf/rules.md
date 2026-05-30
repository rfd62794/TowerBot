# Hard Rules for Cascade Agent

## Branch Protection

**CRITICAL: Never push to main without explicit user approval.**

### Workflow
1. All work happens on `dev` branch
2. Changes must be proven on `dev` (tests passing, spot checks verified)
3. Only after user explicit approval:
   - Merge `dev` to `main`
   - Push `main` to origin

### Commands to Run (Only with User Approval)
```bash
git checkout main
git merge dev
git push origin main
git checkout dev
```

### Forbidden Actions
- Never run `git push origin main` without user approval
- Never merge `dev` to `main` without user approval
- Never switch to `main` branch unless explicitly requested

### Current Branch
Always work on `dev` branch. Verify with:
```bash
git branch
# Should show: * dev
```

## Test Requirements

Before requesting user approval for main merge:
- All tests must pass: `uv run python scripts/verify.py`
- Expected test count: 157/157
- Spot checks must verify key functionality

## Deployment Safety

Changes are only "deploy safe" when:
- All tests pass
- Spot checks verified
- User explicitly approves main merge
