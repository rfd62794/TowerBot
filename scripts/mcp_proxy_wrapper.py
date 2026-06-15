#!/usr/bin/env python3
"""Wrapper for mcp-proxy that reads PRIVYBOT_MCP_URL env var."""

import os
import subprocess
import sys

def main():
    # Get URL from env var or default to Tower
    url = os.getenv("PRIVYBOT_MCP_URL", "http://100.106.80.49:8090/sse")
    
    # Run mcp-proxy with the URL
    cmd = ["uvx", "mcp-proxy", url]
    
    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: uvx not found. Make sure uvx is installed and in PATH.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
