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
- Expected test count: 157/157
- Spot checks must verify key functionality

## Deployment Safety

Changes are only "deploy safe" when:
- All tests pass
- Spot checks verified
- User explicitly approves main merge
