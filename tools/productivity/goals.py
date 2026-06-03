"""Goals, plans, and commitments tools — personal goal tracking system.

Per ADR-038 Phase 2: tasks table deprecated. This module now only handles
goals, milestones, commitments, and weekly plans. Use Google Tasks API for
human task management.
"""

from tools._tool import BaseTool
from infra.db import (
    get_goals,
    get_goal,
    get_milestones,
    get_milestone,
    get_current_weekly_plan,
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

        return self.success({"goal": goal})

    def get_current_plan(self) -> dict:
        """
        Get current weekly plan.

        Returns:
            Dict with weekly plan
        """
        plan = get_current_weekly_plan()
        if not plan:
            return self.success({
                "plan": None,
                "message": "No current weekly plan"
            })

        return self.success({"plan": plan})

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


def suggest_goal_progress(milestone_id: str) -> dict:
    return _goals.suggest_goal_progress(milestone_id)
