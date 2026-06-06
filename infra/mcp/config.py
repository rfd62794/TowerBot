"""MCP server configuration.

Local (Claude Desktop): Expose all tools.
Remote (Tower + Tailscale): JWT protects connection, but write tools
deserve review for security consequences.
"""

from tools.registry import TOOL_REGISTRY
from infra.memory_manager import memory_manager
from infra.mcp.fast import get_state_summary, get_quick_opportunities

# Expose all tools — no allowlist or blocklist
MCP_EXPOSED_TOOLS = set(TOOL_REGISTRY.keys())

# Fast variants for timeout-sensitive MCP calls
# Maps tool name to fast alternative function (SQLite only, no Chroma/Ollama)
MCP_FAST_VARIANTS = {
    "get_memories": memory_manager.search_simple,
    "read_current_state": get_state_summary,
    "find_opportunities": get_quick_opportunities,
}
