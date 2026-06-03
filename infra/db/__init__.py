"""infra.db — Database package.

Re-exports all public functions so external imports are unchanged:
    from infra.db import init_db, add_message, get_channel_history
"""

# CRITICAL: schema.py must be imported first to avoid circular import issues
# Submodules import from schema.py, and schema has _exec/_conn that depend on init_db()
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

# Cache functions - lazy import to avoid circular dependency with manager
def _get_cache_module():
    from infra.db import cache as _cache
    return _cache

def cache_model_list(models: list) -> None:
    return _get_cache_module().cache_model_list(models)

def get_cached_model_list() -> list | None:
    return _get_cache_module().get_cached_model_list()

def cache_tool_result(tool_name: str, params_hash: str, result: dict, ttl_hours: float) -> None:
    return _get_cache_module().cache_tool_result(tool_name, params_hash, result, ttl_hours)

def get_cached_tool_result(tool_name: str, params_hash: str) -> dict | None:
    return _get_cache_module().get_cached_tool_result(tool_name, params_hash)

def get_stale_cached_result(tool_name: str, params_hash: str) -> dict | None:
    return _get_cache_module().get_stale_cached_result(tool_name, params_hash)

def record_preload_result(tool_name: str, params_hash: str, result: dict, ttl_hours: float, success: bool, duration_ms: int, error_msg: str = None) -> None:
    return _get_cache_module().record_preload_result(tool_name, params_hash, result, ttl_hours, success, duration_ms, error_msg)

def get_preload_status() -> list[dict]:
    return _get_cache_module().get_preload_status()

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

from infra.db.goals_milestones import (
    upsert_goal,
    get_goals,
    get_goal,
    upsert_milestone,
    get_milestones,
    get_milestone,
)

from infra.db.commitments_weekly import (
    add_commitment,
    list_commitments,
    upsert_weekly_plan,
    get_current_weekly_plan,
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

from infra.db.autonomous import (
    record_agent_action,
    get_overnight_actions,
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
    "add_commitment", "list_commitments",
    "upsert_weekly_plan", "get_current_weekly_plan",
    "record_deploy", "mark_verify_passed", "mark_stable", "mark_rolled_back",
    "get_last_stable_commit", "get_last_deploy", "get_deploy_history",
    "get_api_state", "upsert_api_state", "log_api_call", "get_call_log", "get_all_api_states",
    "record_poll", "get_last_poll", "get_all_last_polls",
    "record_agent_action", "get_overnight_actions",
]
