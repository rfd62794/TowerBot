"""Seed goals, milestones, tasks, and weekly plans from YAML files."""

import yaml
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import (
    init_db,
    upsert_goal,
    upsert_milestone,
    upsert_task,
    upsert_weekly_plan,
)


def seed_goals():
    """Seed goals and milestones from config/goals.yaml."""
    goals_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "goals.yaml"
    )
    
    with open(goals_path, "r") as f:
        data = yaml.safe_load(f)
    
    for goal in data.get("goals", []):
        goal_id = goal["id"]
        upsert_goal(
            goal_id=goal_id,
            title=goal["title"],
            description=goal.get("description", ""),
            deadline=goal["deadline"],
            status=goal.get("status", "active"),
            progress_pct=goal.get("progress_pct", 0),
            notes=goal.get("notes"),
        )
        
        for milestone in goal.get("milestones", []):
            upsert_milestone(
                milestone_id=milestone["id"],
                goal_id=goal_id,
                title=milestone["title"],
                deadline=milestone["deadline"],
                status=milestone.get("status", "not_started"),
                notes=milestone.get("notes"),
            )
    
    print(f"Seeded {len(data.get('goals', []))} goals with milestones")


def seed_plans():
    """Seed weekly plans and tasks from config/plans.yaml."""
    plans_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "plans.yaml"
    )
    
    with open(plans_path, "r") as f:
        data = yaml.safe_load(f)
    
    # Seed weekly plan
    current_week = data.get("current_week", {})
    if current_week:
        upsert_weekly_plan(
            week_start=current_week["period"].split(" to ")[0],
            week_end=current_week["period"].split(" to ")[1],
            focus=current_week.get("focus", ""),
            notes=current_week.get("notes"),
        )
        print(f"Seeded weekly plan: {current_week['period']}")
    
    # Seed tasks
    tasks = current_week.get("tasks", [])
    for task in tasks:
        scheduled_at = task.get("scheduled")
        if scheduled_at:
            # Convert "2026-05-30 19:00" to datetime format
            scheduled_at = scheduled_at.replace(" ", "T") + ":00"
        
        upsert_task(
            task_id=task["id"],
            title=task["title"],
            due_date=task["due"],
            milestone_id=task.get("milestone_id"),
            scheduled_at=scheduled_at,
            status=task.get("status", "pending"),
        )
    
    print(f"Seeded {len(tasks)} tasks")


def main():
    """Main entry point."""
    print("Initializing database...")
    init_db()
    
    print("Seeding goals and milestones...")
    seed_goals()
    
    print("Seeding weekly plans and tasks...")
    seed_plans()
    
    print("Seed complete.")


if __name__ == "__main__":
    main()
