# Budget Tracking + MCP HTTP Auth — Priority Reorder

Three connected insights requiring implementation. Budget tracking is urgent (autonomous tasks running without cost visibility). MCP HTTP auth is a design conversation.

## 1. OpenRouter Budget Tracking — Build Tonight

**Problem:** Autonomous tasks multiplied LLM call rate. Three tasks running every 30-120 minutes means potential paid model fallbacks while sleeping. No cost visibility.

**Solution:** Hard cap on paid usage with immediate Telegram alerts.

### Implementation
- New `openrouter_usage` table:
  ```sql
  task_context, model, is_free, prompt_tokens,
  completion_tokens, estimated_cost_usd, called_at
  ```
- Add to `model_manager.py`:
  ```python
  MAX_DAILY_PAID_USD = 0.10  # hard cap

  def can_use_paid_model() -> bool:
      today_cost = get_today_paid_cost()
      return today_cost < MAX_DAILY_PAID_USD
  ```
- In `_rotate()`: if `can_use_paid_model()` is False, return stale cache or skip tool call
- Every model call logged to DB
- Paid calls trigger immediate Telegram alert
- `/status` shows today's cost, this week's cost, free vs paid ratio

**Priority:** Tonight — autonomous tasks running now with no visibility.

## 2. Token-Gated MCP — HTTP/SSE + Auth

**Problem:** ADR-033 stdio design only works when Claude Desktop and PrivyBot are on same machine. Need remote access.

**Solution:** HTTP/SSE transport with short-lived JWT tokens.

### Architecture
```
Robert → /mcp_token 60 (Telegram)
PrivyBot → generates signed JWT, 1hr expiry
PrivyBot → sends token to Robert via Telegram

Robert → pastes token into Claude.ai conversation
Claude → connects to https://[host]/mcp with Bearer token
Claude → calls all 52 tools live
Token expires → access revoked
```

### Implementation
- ADR-033 update: stdio → HTTP/SSE transport
- Add token auth layer
- Add `/mcp_token [minutes]` Telegram command
- **Tailscale Funnel for public URL:**
  ```powershell
  tailscale funnel --bg 8090
  ```
  - Public URL: `https://[device].[tailnet].ts.net`
  - No router config, no static IP, no dynamic DNS
  - Automatic HTTPS certificate
  - Free tier includes Funnel
  - Stable URL as long as device name doesn't change
  - Tower deployment: move Funnel there for always-on prod URL

**Capability:** Query live data, add memories, check autonomous status from any Claude conversation — not just Desktop.

**Priority:** After budget tracking — needs ADR-033 design conversation first.

## 3. Priority Reorder

**Before:** mem0 → MCP → httpx → Ollama
**After:** Budget tracking → MCP (HTTP+auth) → mem0 → Ollama

**Rationale:**
- Budget tracking: protects overnight operation right now
- MCP: unlocks Claude ↔ PrivyBot direct integration
- mem0: intelligence quality improvement, not urgent

## Tonight vs. Next Session

**Tonight:** Build budget tracking
- DB table + model_manager changes + /status update
- Autonomous tasks running with no cost visibility

**Next session:** Start MCP HTTP+auth design conversation
- ADR-033 update first
- Then implementation

## Current State

- 4 autonomous tasks running overnight
- No cost visibility
- First 7AM briefing tomorrow will show overnight actions
