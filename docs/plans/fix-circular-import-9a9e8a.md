# Fix Circular Import in Memory Tools

Remove memory tool imports and registry entries from tools/__init__.py to break circular import chain. Memory tools are already handled in core/agent.py via MEMORY_TOOL_DEFINITIONS.

## Changes

**tools/__init__.py:**
- Remove `from core.memory import (tool_save_memory, tool_update_memory, tool_retire_memory, tool_get_memories)`
- Remove `save_memory`, `update_memory`, `retire_memory`, `get_memories` from TOOL_REGISTRY

## Verification

After fix, run `uv run python scripts/verify.py` should show 192/192 passed.
