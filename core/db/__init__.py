"""core.db — Database package.

Re-exports all public functions so external imports are unchanged:
    from core.db import init_db, add_message, get_channel_history
"""

from core.db.schema import DB_PATH, init_db, _exec

from core.db.threads import (
    create_thread,
    update_thread_name,
    update_thread_active,
    list_threads,
)

from core.db.messages import (
    add_message,
    get_context,
)

from core.db.memory import (
    save_memory,
    update_memory,
    retire_memory,
    get_memories,
    list_memories,
)

from core.db.models import (
    record_throttle,
    record_success,
    get_throttled_models,
    get_model_status_all,
)

from core.db.cache import (
    cache_model_list,
    get_cached_model_list,
    cache_tool_result,
    get_cached_tool_result,
)

from core.db.history import (
    record_channel_day,
    get_channel_history,
    record_video_day,
    get_video_history,
    record_game_day,
    get_game_history,
    record_weather_day,
    get_weather_history,
    upsert_video_metadata,
    get_video_metadata,
    get_all_video_metadata,
    upsert_scheduled_video,
    get_scheduled_videos,
    clear_old_scheduled,
)

from core.db.queue import (
    queue_observation,
    get_pending_observations,
    mark_sent,
    flush_morning_queue,
)

from core.db.goals import (
    upsert_goal,
    get_goals,
    get_goal,
    upsert_milestone,
    get_milestones,
    get_milestone,
    upsert_task,
    get_tasks,
    get_task,
    update_task_status,
    get_tasks_due_today,
    get_upcoming_scheduled,
    upsert_weekly_plan,
    get_current_weekly_plan,
)

__all__ = [
    "DB_PATH", "init_db",
    "create_thread", "update_thread_name", "update_thread_active", "list_threads",
    "add_message", "get_context",
    "save_memory", "update_memory", "retire_memory", "get_memories", "list_memories",
    "record_throttle", "record_success", "get_throttled_models", "get_model_status_all",
    "cache_model_list", "get_cached_model_list", "cache_tool_result", "get_cached_tool_result",
    "record_channel_day", "get_channel_history", "record_video_day", "get_video_history",
    "record_game_day", "get_game_history", "record_weather_day", "get_weather_history",
    "upsert_video_metadata", "get_video_metadata", "get_all_video_metadata",
    "upsert_scheduled_video", "get_scheduled_videos", "clear_old_scheduled",
    "queue_observation", "get_pending_observations", "mark_sent", "flush_morning_queue",
    "upsert_goal", "get_goals", "get_goal",
    "upsert_milestone", "get_milestones", "get_milestone",
    "upsert_task", "get_tasks", "get_task", "update_task_status",
    "get_tasks_due_today", "get_upcoming_scheduled",
    "upsert_weekly_plan", "get_current_weekly_plan",
]
