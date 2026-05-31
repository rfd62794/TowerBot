"""MCP server configuration.

Local (Claude Desktop): Expose all tools except internal bot plumbing.
Remote (Tower + Tailscale): JWT protects connection, but write tools
deserve review for security consequences.
"""

from tools.registry import TOOL_REGISTRY

# Internal bot plumbing with no value when called externally
MCP_EXCLUDED = {
    "name_thread",   # bot-internal state, meaningless externally
    "sync",          # Google Tasks sync managed by bot scheduler
}

# Expose all tools except internal plumbing
MCP_EXPOSED_TOOLS = {
    k for k in TOOL_REGISTRY.keys()
    if k not in MCP_EXCLUDED
}
