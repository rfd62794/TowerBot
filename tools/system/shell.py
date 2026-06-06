import subprocess
import logging
import re
from typing import Optional

logger = logging.getLogger("privy.shell")

ALLOWED_VERBS = {
    "nssm", "uv", "git", "python", "pytest",
    "tasklist", "dir", "echo", "ping", "curl",
    "systeminfo", "ver", "findstr", "powershell", "cargo",
}

BLOCKED_PATTERNS = [
    "rm ", "del ", "rmdir", "rd ", "format",
    "&&", "||", ";", "`", "$(", "${",
    " > ", " >> ", " 2>",
    "-rf", "/f /s", "/s /q",
    "wget", "invoke-expression", "iex ",
    "runas", "reg ", "regedit", "schtasks",
]

NAMED_COMMANDS = {
    "privy_tests":     {"command": "uv run pytest",            "cwd": "C:/Github/PrivyBot", "description": "Run PrivyBot test suite"},
    "list_services":   {"command": "nssm list",                "cwd": None,                 "description": "List NSSM services"},
    "restart_privy":   {"command": "nssm restart PrivyBot",    "cwd": None,                 "description": "Restart PrivyBot service"},
    "restart_mcp":     {"command": "nssm restart PrivybotMCP", "cwd": None,                 "description": "Restart PrivyBot MCP service"},
    "privy_status":    {"command": "git status",               "cwd": "C:/Github/PrivyBot", "description": "Git status for PrivyBot"},
    "privy_pull":      {"command": "git pull",                 "cwd": "C:/Github/PrivyBot", "description": "Pull latest PrivyBot changes"},
    "privy_log":       {"command": "git log --oneline -10",    "cwd": "C:/Github/PrivyBot", "description": "Last 10 commits"},
    "tower_processes": {"command": "tasklist | findstr python", "cwd": None,                "description": "Running Python processes"},
}


def _check_command(command: str) -> tuple[bool, str]:
    """Returns (allowed, reason). Called before any execution."""
    verb = command.strip().split()[0].lower() if command.strip() else ""
    if verb not in ALLOWED_VERBS:
        return False, f"verb '{verb}' not in approved list"
    cmd_lower = command.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in cmd_lower:
            return False, f"blocked pattern '{pattern}' detected"
    return True, "ok"


def run_named_command(name: str) -> dict:
    """Run a pre-approved named command from the registry."""
    if name not in NAMED_COMMANDS:
        return {
            "success": False,
            "error": "unknown command",
            "available": list(NAMED_COMMANDS.keys())
        }
    
    cmd_info = NAMED_COMMANDS[name]
    command = cmd_info["command"]
    cwd = cmd_info["cwd"]
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Parse pytest output if this is the test command
        if name == "privy_tests":
            output = result.stdout + result.stderr
            # Look for "X passed, Y failed, Z skipped" pattern
            match = re.search(r"(\d+)\s+passed,\s*(\d+)\s+failed,\s*(\d+)\s+skipped", output)
            if match:
                return {
                    "success": True,
                    "command": name,
                    "passed": int(match.group(1)),
                    "failed": int(match.group(2)),
                    "skipped": int(match.group(3)),
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
        
        return {
            "success": result.returncode == 0,
            "command": name,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "timeout",
            "command": name
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "command": name
        }


def execute_shell(command: str, timeout: int = 30, working_dir: Optional[str] = None) -> dict:
    """Run a filtered shell command. Both filter stages must pass."""
    allowed, reason = _check_command(command)
    
    if not allowed:
        logger.warning(f"[shell] blocked command: {command} - {reason}")
        return {
            "success": False,
            "blocked": True,
            "reason": reason,
            "command": command
        }
    
    logger.info(f"[shell] executing: {command}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return {
            "success": result.returncode == 0,
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "timeout",
            "command": command
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "command": command
        }


def list_named_commands() -> dict:
    """Return all registered named commands and their descriptions."""
    return {
        "commands": {
            name: {
                "command": info["command"],
                "description": info["description"],
                "cwd": info["cwd"]
            }
            for name, info in NAMED_COMMANDS.items()
        }
    }
