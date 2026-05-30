"""Goals, plans, and tasks tools — personal goal tracking system."""

from tools._tool import BaseTool
from infra.db import (
    get_goals,
    get_goal,
    get_milestones,
    get_milestone,
    get_tasks,
    get_task,
    update_task_status,
    get_tasks_due_today,
    get_upcoming_scheduled,
    get_current_weekly_plan,
    upsert_task,
    add_commitment,
    list_commitments,
)


def get_goals_list(status: str = None) -> dict:
    """
    Get list of goals with optional status filter.

    Args:
        status: Optional status filter (active, complete, paused)

    Returns:
        Dict with count and list of goals
    """
    goals = get_goals(status=status)
    
    # Enrich with milestones
    for goal in goals:
        goal["milestones"] = get_milestones(goal_id=goal["id"])
    
    return {
        "count": len(goals),
        "goals": goals
    }


def get_tasks_today() -> dict:
    """
    Get tasks due today.

    Returns:
        Dict with count and list of today's tasks
    """
    tasks = get_tasks_due_today()
    
    return {
        "count": len(tasks),
        "tasks": tasks
    }


def get_upcoming_tasks(hours: int = 24) -> dict:
    """
    Get upcoming scheduled tasks within specified hours.

    Args:
        hours: Hours to look ahead (default: 24)

    Returns:
        Dict with count and list of upcoming tasks
    """
    tasks = get_upcoming_scheduled(hours=hours)
    
    return {
        "count": len(tasks),
        "tasks": tasks
    }


def add_new_task(title: str, due_date: str, scheduled_at: str = None, 
                 milestone_id: str = None) -> dict:
    """
    Add a new task.

    Args:
        title: Task title
        due_date: Due date (YYYY-MM-DD)
        scheduled_at: Optional scheduled datetime (YYYY-MM-DD HH:MM)
        milestone_id: Optional milestone ID to link to

    Returns:
        Dict with created task
    """
    # Generate task ID
    import uuid
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    
    # Format scheduled_at if provided
    if scheduled_at:
        scheduled_at = scheduled_at.replace(" ", "T") + ":00"
    
    upsert_task(
        task_id=task_id,
        title=title,
        due_date=due_date,
        scheduled_at=scheduled_at,
        milestone_id=milestone_id,
        status="pending"
    )
    
    return get_task(task_id)


def save_commitment(description: str, deadline: str = None) -> dict:
    """
    Save a commitment Robert has made.

    Args:
        description: What Robert committed to do
        deadline: When — YYYY-MM-DD or natural language like
                  "this weekend", "after June 15", "end of month". Optional.

    Returns:
        Dict with status, description, deadline, commitment_id
    """
    commitment_id = add_commitment(description=description, deadline=deadline)
    return {
        "status": "saved",
        "description": description,
        "deadline": deadline or "no deadline set",
        "commitment_id": commitment_id,
    }


class GoalsTools(BaseTool):
    """Goals tools with BaseTool pattern for consistent error returns."""

    def get_goal_detail(self, goal_id: str) -> dict:
        """
        Get detailed information about a specific goal.

        Args:
            goal_id: Goal ID

        Returns:
            Dict with goal details and milestones
        """
        goal = get_goal(goal_id)
        if not goal:
            return self.error(f"Goal not found: {goal_id}", code="not_found")
        
        goal["milestones"] = get_milestones(goal_id=goal_id)
        
        # Get tasks for each milestone
        for milestone in goal["milestones"]:
            milestone["tasks"] = get_tasks(milestone_id=milestone["id"])
        
        return self.success({"goal": goal})

    def get_current_plan(self) -> dict:
        """
        Get current weekly plan with tasks.

        Returns:
            Dict with weekly plan and associated tasks
        """
        plan = get_current_weekly_plan()
        if not plan:
            return self.success({
                "plan": None,
                "message": "No current weekly plan"
            })
        
        # Get all tasks for this week
        tasks = get_tasks(due_date=plan["week_end"])
        
        return self.success({
            "plan": plan,
            "tasks": tasks
        })

    def update_task(self, task_id: str, status: str) -> dict:
        """
        Update task status.

        Args:
            task_id: Task ID
            status: New status (pending, in_progress, complete, cancelled)

        Returns:
            Dict with updated task
        """
        task = get_task(task_id)
        if not task:
            return self.error(f"Task not found: {task_id}", code="not_found")
        
        update_task_status(task_id, status)
        
        # Return updated task
        updated = get_task(task_id)
        return self.success(updated)

    def suggest_goal_progress(self, milestone_id: str) -> dict:
        """
        Suggest goal progress update based on milestone.

        Args:
            milestone_id: Milestone ID

        Returns:
            Dict with suggestion text for Telegram
            Does NOT update — agent suggests only
        """
        milestone = get_milestone(milestone_id)
        if not milestone:
            return self.error(f"Milestone not found: {milestone_id}", code="not_found")
        
        goal = get_goal(milestone["goal_id"])
        if not goal:
            return self.error(f"Goal not found for milestone: {milestone_id}", code="not_found")
        
        suggestion = (
            f"Sounds like the milestone '{milestone['title']}' "
            f"for goal '{goal['title']}' might be complete. "
            f"Mark it done? /confirm {milestone_id} or /reject {milestone_id}"
        )
        
        return self.success({
            "suggestion": suggestion,
            "milestone_id": milestone_id,
            "goal_id": goal["id"],
            "milestone_title": milestone["title"],
            "goal_title": goal["title"]
        })


# Module-level instance
_goals = GoalsTools()


# Backwards compat wrappers — registry unchanged
def get_goal_detail(goal_id: str) -> dict:
    return _goals.get_goal_detail(goal_id)


def get_current_plan() -> dict:
    return _goals.get_current_plan()


def update_task(task_id: str, status: str) -> dict:
    return _goals.update_task(task_id, status)


def suggest_goal_progress(milestone_id: str) -> dict:
    return _goals.suggest_goal_progress(milestone_id)
