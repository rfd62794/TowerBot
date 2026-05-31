"""
tools/meta.py

Meta-tools that help the agent reason.
No API calls. No caching. No stale data.
Simple passthrough functions only.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import math

EASTERN = ZoneInfo("America/New_York")


def think(content: str) -> dict:
    """
    Record a reasoning step before acting.
    Creates a visible scratchpad entry.

    Provides context continuity when
    models switch due to throttling —
    the next model sees the thought
    and can continue from it.

    Returns immediately. No side effects.
    """
    return {
        "ok": True,
        "thought": content,
        "stale_notice": None
    }


def get_current_datetime() -> dict:
    """Return current datetime in Eastern time. No API, no cache."""
    now = datetime.now(EASTERN)
    return {
        "ok": True,
        "stale_notice": None,
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "day_of_week": now.strftime("%A"),
        "timezone": "America/New_York",
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
