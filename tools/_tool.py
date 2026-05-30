"""
tools/_tool.py

Base class for all tools/*.py files.
Enforces consistent return shape.
All tool functions return success() or error().
Agent always gets ok, stale_notice, data.
"""


class BaseTool:
    """
    Base class for all tool handlers.

    Enforces consistent return shape.
    All tool functions return success() or error().
    Agent always gets ok, stale_notice, data.
    """

    def success(self, data: dict, stale_result: dict = None) -> dict:
        """
        Standard success return shape.
        stale_result: the raw API result if it contained stale metadata.
        Pass it here and BaseTool extracts the stale_notice automatically.
        """
        from infra.cache import cache

        # Strip internal keys from data
        clean = {k: v for k, v in data.items() if not k.startswith("_")}
        result = {"ok": True, "stale_notice": None, **clean}

        if stale_result is not None:
            notice = cache.stale_notice(stale_result)
            result["stale_notice"] = notice

        return result

    def error(self, message: str, code: str = None) -> dict:
        """
        Standard error return shape.
        Agent sees ok=False and error message.
        """
        return {"ok": False, "error": message, "error_code": code, "stale_notice": None}

    def stale_notice(self, result: dict) -> str | None:
        """Convenience wrapper."""
        from infra.cache import cache

        return cache.stale_notice(result)
