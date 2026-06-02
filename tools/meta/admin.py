"""Admin tools for database maintenance and cleanup."""

from infra.db.schema import _exec


def purge_null_tasks() -> dict:
    """Admin: cancel all queued tasks with null or empty prompts."""
    cur = _exec(
        "UPDATE task_queue SET status='cancelled' "
        "WHERE (prompt IS NULL OR prompt='') AND status='queued'",
        commit=True
    )
    return {"cancelled": cur.rowcount, "status": "success"}


def get_logs(lines: int = 50, filter_str: str = None) -> dict:
    """
    Read the tail of Tower's PrivyBot log file.

    PARAMS:
      lines (int): number of log lines to return. Default 50, max 200.
      filter_str (str): optional keyword filter — only return lines
                        containing this string (case-insensitive).

    RETURNS: dict with keys:
      ok (bool)
      log_path (str)
      total_lines (int): lines returned after filter
      lines (list[str]): the log lines
      filtered (bool): whether filter_str was applied
      error (str): present only on failure
    """
    import os
    from pathlib import Path

    log_path = os.environ.get(
        "PRIVYBOT_LOG_PATH",
        str(Path(__file__).parent.parent.parent / "logs" / "privybot.log")
    )

    lines = min(max(1, lines), 200)

    try:
        if not os.path.exists(log_path):
            return {
                "ok": False,
                "error": f"Log file not found: {log_path}",
                "log_path": log_path
            }

        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        tail = [line.rstrip() for line in tail]

        filtered = False
        if filter_str:
            tail = [l for l in tail if filter_str.lower() in l.lower()]
            filtered = True

        return {
            "ok": True,
            "log_path": log_path,
            "total_lines": len(tail),
            "lines": tail,
            "filtered": filtered
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "log_path": log_path
        }


def run_diagnostic() -> dict:
    """
    Aggregate health check for Tower's PrivyBot instance.

    RETURNS: dict with keys:
      ok (bool)
      git_head (str): current 7-char commit hash
      queue_depth (int): total queued tasks
      null_task_count (int): queued tasks with null/empty prompt
      memory_count (int): total memory rows in DB
      chroma_status (str): 'ok' | 'error' | 'unavailable'
      recent_errors (list[str]): last 5 error log lines
      last_failed_tasks (list[dict]): last 5 failed tasks with
                                      id, name, prompt_preview, error
      error (str): present only on top-level failure
    """
    import subprocess
    from pathlib import Path

    result = {"ok": True}

    # Git HEAD
    try:
        git = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parent.parent.parent)
        )
        result["git_head"] = git.stdout.strip() if git.returncode == 0 \
            else "unknown"
    except Exception:
        result["git_head"] = "unknown"

    # Queue depth
    try:
        rows = _exec(
            "SELECT COUNT(*) as c FROM task_queue WHERE status='queued'"
        )
        result["queue_depth"] = rows[0]["c"] if rows else 0
    except Exception as e:
        result["queue_depth"] = -1
        result["queue_error"] = str(e)

    # Null task count
    try:
        rows = _exec(
            """SELECT COUNT(*) as c FROM task_queue
               WHERE (prompt IS NULL OR prompt='') AND status='queued'"""
        )
        result["null_task_count"] = rows[0]["c"] if rows else 0
    except Exception:
        result["null_task_count"] = -1

    # Memory count
    try:
        rows = _exec(
            "SELECT COUNT(*) as c FROM memory WHERE active=1"
        )
        result["memory_count"] = rows[0]["c"] if rows else 0
    except Exception:
        result["memory_count"] = -1

    # Chroma status
    # KNOWN COMPROMISE: MemoryManager has no public heartbeat method.
    # Using private _get_collection() as best available signal.
    # If Chroma init fails, this will catch the exception.
    try:
        from infra.memory_manager import memory_manager
        collection = memory_manager._get_collection()
        if collection is None:
            result["chroma_status"] = "unavailable"
        else:
            result["chroma_status"] = "ok"
    except ImportError:
        result["chroma_status"] = "unavailable"
    except Exception as e:
        result["chroma_status"] = f"error: {str(e)[:80]}"

    # Recent errors from log
    log_result = get_logs(lines=200, filter_str="ERROR")
    if log_result.get("ok"):
        result["recent_errors"] = log_result["lines"][-5:]
    else:
        result["recent_errors"] = []

    # Last failed tasks
    try:
        rows = _exec(
            """SELECT id, task_name, prompt, result
               FROM task_queue WHERE status='failed'
               ORDER BY updated_at DESC LIMIT 5"""
        )
        result["last_failed_tasks"] = [
            {
                "id": r["id"],
                "name": r["task_name"] or "unnamed",
                "prompt_preview": (r["prompt"] or "")[:80],
                "error": (r["result"] or "")[:120]
            }
            for r in (rows or [])
        ]
    except Exception:
        result["last_failed_tasks"] = []

    return result

