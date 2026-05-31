"""Fast variants for slow MCP tools.

Lightweight alternatives for timeout-sensitive calls.
"""

import subprocess
import sys
from pathlib import Path

# Add project root to path
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env")

from infra.db import init_db, get_overnight_actions
from infra.memory_manager import memory_manager

init_db()


def get_state_summary() -> dict:
    """Lightweight version of read_current_state — DB + git log, no file reads."""
    # Last commit from git
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            cwd=_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        last_commit = result.stdout.strip() or "unknown"
    except Exception:
        last_commit = "unknown"

    # Overnight actions from DB
    try:
        overnight = get_overnight_actions(hours=12)
        overnight_summary = [{"task_name": a.get("task_name", "unknown"), "ran_at": a.get("ran_at", "")} for a in overnight]
    except Exception:
        overnight_summary = []

    return {
        "ok": True,
        "last_commit": last_commit,
        "overnight_actions": len(overnight_summary),
        "overnight_summary": overnight_summary,
    }


def get_quick_opportunities() -> dict:
    """Read last self_expansion_planner result from DB instead of re-running analysis."""
    try:
        from infra.db.autonomous import get_overnight_actions
        actions = get_overnight_actions(hours=24)
        
        # Find most recent self_expansion_planner result
        for action in actions:
            if action.get("task_name") == "self_expansion_planner":
                return {
                    "ok": True,
                    "source": "last_self_expansion_planner_run",
                    "result": action.get("result", "No result recorded"),
                    "ran_at": action.get("ran_at"),
                }
        
        return {
            "ok": True,
            "source": "last_self_expansion_planner_run",
            "result": "No run recorded yet",
            "ran_at": None,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }
