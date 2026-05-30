"""infra.db — Database package.

Re-exports all public functions so external imports are unchanged:
    from infra.db import init_db, add_message, get_channel_history
"""

from infra.db.schema import DB_PATH, init_db, _exec

from infra.db.threads import (
    create_thread,
    update_thread_name,
    update_thread_active,
    list_threads,
)

from infra.db.messages import (
    add_message,
    get_context,
)

from infra.db.memory import (
    save_memory,
    update_memory,
    retire_memory,
    get_memories,
    list_memories,
)

from infra.db.models import (
    record_throttle,
    record_success,
    get_throttled_models,
    get_model_status_all,
)

from infra.db.cache import (
    cache_model_list,
    get_cached_model_list,
    cache_tool_result,
    get_cached_tool_result,
    get_stale_cached_result,
    record_preload_result,
    get_preload_status,
)

from infra.db.history import (
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

from infra.db.queue import (
    queue_observation,
    get_pending_observations,
    mark_sent,
    flush_morning_queue,
)

from infra.db.goals import (
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
    add_commitment,
    list_commitments,
)

from infra.db.personal_tasks import (
    add_personal_task,
    get_personal_tasks,
    get_tasks_due_soon,
    complete_personal_task,
    snooze_personal_task,
    delete_personal_task,
    mark_reminded,
    already_reminded,
    set_google_task_id,
    get_unsynced_tasks,
    get_tasks_completed_since,
    update_sync_record,
    get_last_sync,
)

from infra.db.deployments import (
    record_deploy,
    mark_verify_passed,
    mark_stable,
    mark_rolled_back,
    get_last_stable_commit,
    get_last_deploy,
    get_deploy_history,
)

from infra.db.rate_limits_db import (
    get_api_state,
    upsert_api_state,
    log_api_call,
    get_call_log,
    get_all_api_states,
)

from infra.db.polling_db import (
    record_poll,
    get_last_poll,
    get_all_last_polls,
)

__all__ = [
    "DB_PATH", "init_db",
    "create_thread", "update_thread_name", "update_thread_active", "list_threads",
    "add_message", "get_context",
    "save_memory", "update_memory", "retire_memory", "get_memories", "list_memories",
    "record_throttle", "record_success", "get_throttled_models", "get_model_status_all",
    "cache_model_list", "get_cached_model_list", "cache_tool_result", "get_cached_tool_result",
    "get_stale_cached_result", "record_preload_result", "get_preload_status",
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
    "add_commitment", "list_commitments",
    "add_personal_task", "get_personal_tasks", "get_tasks_due_soon",
    "complete_personal_task", "snooze_personal_task", "delete_personal_task",
    "mark_reminded", "already_reminded",
    "set_google_task_id", "get_unsynced_tasks", "get_tasks_completed_since",
    "update_sync_record", "get_last_sync",
    "record_deploy", "mark_verify_passed", "mark_stable", "mark_rolled_back",
    "get_last_stable_commit", "get_last_deploy", "get_deploy_history",
    "get_api_state", "upsert_api_state", "log_api_call", "get_call_log", "get_all_api_states",
    "record_poll", "get_last_poll", "get_all_last_polls",
]
