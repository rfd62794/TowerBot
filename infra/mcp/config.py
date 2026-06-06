"""MCP server configuration.

Local (Claude Desktop): Expose all tools except internal bot plumbing.
Remote (Tower + Tailscale): JWT protects connection, but write tools
deserve review for security consequences.
"""

from tools.registry import TOOL_REGISTRY
from infra.memory_manager import memory_manager
from infra.mcp.fast import get_state_summary, get_quick_opportunities

# Internal bot plumbing with no value when called externally
MCP_EXCLUDED = {
    "name_thread",   # bot-internal state, meaningless externally
    "sync",          # Google Tasks sync managed by bot scheduler
    "think",         # bot-internal reasoning tool, meaningless externally
}

# Expose all tools except internal plumbing
MCP_EXPOSED_TOOLS = {
    k for k in TOOL_REGISTRY.keys()
    if k not in MCP_EXCLUDED
}

# Fast variants for timeout-sensitive MCP calls
# Maps tool name to fast alternative function (SQLite only, no Chroma/Ollama)
MCP_FAST_VARIANTS = {
    "get_memories": memory_manager.search_simple,
    "read_current_state": get_state_summary,
    "find_opportunities": get_quick_opportunities,
}
