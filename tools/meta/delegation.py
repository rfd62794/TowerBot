"""Delegation tools for Claude → PrivyBot task queue."""

from tools._tool import BaseTool
from infra.db.task_queue import add_task, get_task_status, list_pending, cancel_task as _cancel


class DelegationTools(BaseTool):

    def queue_task(
        self,
        prompt: str,
        task_name: str = "delegated",
        context: str = None,
        priority: str = "normal",
        run_immediately: bool = True,
    ) -> dict:
        """Queue a task for PrivyBot to execute."""
        task_id = add_task(
            prompt=prompt,
            task_name=task_name,
            context=context,
            priority=priority,
            source="claude",
            run_at=None if run_immediately else None,
        )
        return self.success({
            "task_id": task_id,
            "status": "queued",
            "estimated_start": "within 60 seconds",
            "priority": priority,
        })

    def get_task_result(self, task_id: int) -> dict:
        """Check status and result of a delegated task."""
        task = get_task_status(task_id)
        if not task:
            return self.error(
                f"Task {task_id} not found",
                code="not_found"
            )
        return self.success({
            "task_id": task_id,
            "status": task["status"],
            "prompt_preview": (task.get("prompt") or "")[:100],
            "result": task.get("result"),
            "duration_ms": task.get("duration_ms"),
            "queued_at": task.get("created_at"),
            "completed_at": task.get("completed_at"),
        })

    def list_pending_tasks(self) -> dict:
        """List all queued and running delegated tasks."""
        tasks = list_pending()
        return self.success({
            "count": len(tasks),
            "tasks": [
                {
                    "task_id": t["id"],
                    "task_name": t.get("task_name"),
                    "status": t["status"],
                    "priority": t.get("priority"),
                    "prompt_preview": (t.get("prompt") or "")[:80],
                    "queued_at": t.get("created_at"),
                }
                for t in tasks
            ]
        })

    def cancel_task(self, task_id: int) -> dict:
        """Cancel a queued task before it starts."""
        cancelled = _cancel(task_id)
        if not cancelled:
            return self.error(
                f"Task {task_id} cannot be cancelled "
                "(already running, complete, or not found)",
                code="cancel_failed"
            )
        return self.success({
            "task_id": task_id,
            "status": "cancelled"
        })


delegation_tools = DelegationTools()
