#!/usr/bin/env python3
"""Wrapper for mcp_stdio_proxy.py that reads PRIVYBOT_MCP_URL env var."""

import os
import subprocess
import sys

def main():
    # Get URL from env var or default to Tower
    url = os.getenv("PRIVYBOT_MCP_URL", "http://100.106.80.49:8090/sse")
    
    # Set env var for the proxy script
    env = os.environ.copy()
    env["MCP_SSE_URL"] = url
    
    # Run mcp_stdio_proxy.py with the URL in env var
    cmd = [sys.executable, "C:\\Github\\PrivyBot\\scripts\\mcp_stdio_proxy.py"]
    
    try:
        result = subprocess.run(cmd, env=env, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: mcp_stdio_proxy.py not found at C:\\Github\\PrivyBot\\scripts\\mcp_stdio_proxy.py", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
