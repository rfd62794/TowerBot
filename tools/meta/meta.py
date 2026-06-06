"""
tools/meta.py

Meta-tools that help the agent reason.
No API calls. No caching. No stale data.
Simple passthrough functions only.
"""

from datetime import datetime
import math
import subprocess
from pathlib import Path

PRIVYBOT_REPO = Path("C:/Github/PrivyBot")


def think(content: str = None, thought: str = None, plan: str = None, **kwargs) -> dict:
    """
    Record a reasoning step before acting.
    Creates a visible scratchpad entry.

    Provides context continuity when
    models switch due to throttling —
    the next model sees the thought
    and can continue from it.

    Returns immediately. No side effects.
    """
    actual = content or thought or plan or ""
    return {
        "ok": True,
        "thought": actual,
        "stale_notice": None
    }


def get_current_datetime() -> dict:
    """Return current datetime in local timezone. No API, no cache."""
    now = datetime.now()
    # Get local timezone info
    tz = now.astimezone().tzinfo
    tz_name = str(tz) if tz else "Local"
    return {
        "ok": True,
        "stale_notice": None,
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "day_of_week": now.strftime("%A"),
        "timezone": tz_name,
        "timestamp": int(now.timestamp()),
    }


def calculate(expression: str) -> dict:
    """Safe math evaluator. No eval of arbitrary Python."""
    _safe = {
        "__builtins__": {},
        "abs": abs, "round": round,
        "sqrt": math.sqrt, "floor": math.floor, "ceil": math.ceil,
        "log": math.log, "log10": math.log10,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "pi": math.pi, "e": math.e,
    }
    try:
        result = eval(
            compile(expression, "<string>", "eval"), _safe
        )
        return {
            "ok": True,
            "stale_notice": None,
            "expression": expression,
            "result": result,
            "result_str": str(result),
        }
    except ZeroDivisionError:
        return {"ok": False, "error": "Division by zero",
                "stale_notice": None}
    except Exception as e:
        return {"ok": False, "error": str(e), "stale_notice": None}


def run_openagent(
    command: str = "analyze",
    context: str = None,
    repo_path: str = None
) -> dict:
    """Run OpenAgent CLI on a repository. No cache — always fresh."""
    repo = Path(repo_path) if repo_path else PRIVYBOT_REPO

    cmd = ["uv", "run", "openagent", command]
    if context and command == "analyze":
        cmd += ["--context", context]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(repo)
        )
        if result.returncode != 0:
            return {
                "ok": False,
                "stale_notice": None,
                "error": result.stderr.strip() or "OpenAgent command failed",
                "error_code": "openagent_failed"
            }
        return {
            "ok": True,
            "stale_notice": None,
            "command": command,
            "repo": str(repo),
            "context": context,
            "output": result.stdout.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stale_notice": None,
                "error": "OpenAgent timed out (120s)",
                "error_code": "timeout"}
    except FileNotFoundError:
        return {"ok": False, "stale_notice": None,
                "error": "openagent not found — run: uv add openagent-directive",
                "error_code": "not_installed"}
