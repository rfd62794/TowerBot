"""History and metadata tables: channel, video, game, weather, scheduled videos."""

from infra.db.schema import _exec


def record_channel_day(date: str, views: int, watch_time: float, subs: int) -> None:
    """Record daily channel metrics."""
    _exec(
        "INSERT OR REPLACE INTO channel_history (date, views, watch_time_minutes, subscribers_gained) "
        "VALUES (?, ?, ?, ?)",
        (date, views, watch_time, subs), commit=True,
    )


def get_channel_history(days: int = 30) -> list[dict]:
    """Get channel history for last N days."""
    rows = _exec(
        "SELECT date, views, watch_time_minutes, subscribers_gained, recorded_at "
        "FROM channel_history "
        "WHERE date >= date('now', '-' || ? || ' days') "
        "ORDER BY date ASC",
        (days,),
    ).fetchall()
    return [dict(r) for r in rows]


def record_video_day(video_id: str, date: str, views: int, watch_time: float,
                     avg_duration: float, avg_pct: float) -> None:
    _exec(
        "INSERT OR REPLACE INTO video_history "
        "(video_id, date, views, watch_time_minutes, avg_view_duration_seconds, avg_view_percentage) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (video_id, date, views, watch_time, avg_duration, avg_pct), commit=True,
    )


def get_video_history(video_id: str, days: int = 30) -> list[dict]:
    rows = _exec(
        "SELECT * FROM video_history WHERE video_id = ? "
        "AND date >= date('now', '-' || ? || ' days') ORDER BY date DESC",
        (video_id, days),
    ).fetchall()
    return [dict(r) for r in rows]


def record_game_day(appid: int, date: str, players_2weeks: int,
                    owners_low: int, owners_high: int, price_usd: float, on_sale: bool) -> None:
    _exec(
        "INSERT OR REPLACE INTO game_history "
        "(appid, date, players_2weeks, owners_low, owners_high, price_usd, on_sale) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (appid, date, players_2weeks, owners_low, owners_high, price_usd, 1 if on_sale else 0), commit=True,
    )


def get_game_history(appid: int, days: int = 90) -> list[dict]:
    rows = _exec(
        "SELECT * FROM game_history WHERE appid = ? "
        "AND date >= date('now', '-' || ? || ' days') ORDER BY date DESC",
        (appid, days),
    ).fetchall()
    return [dict(r) for r in rows]


def record_weather_day(date: str, temp_f: float, condition: str, wind_mph: float) -> None:
    _exec(
        "INSERT OR REPLACE INTO weather_history (date, temp_f, condition, wind_mph) "
        "VALUES (?, ?, ?, ?)",
        (date, temp_f, condition, wind_mph), commit=True,
    )


def get_weather_history(days: int = 30) -> list[dict]:
    rows = _exec(
        "SELECT * FROM weather_history WHERE date >= date('now', '-' || ? || ' days') "
        "ORDER BY date DESC",
        (days,),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_video_metadata(video_id: str, title: str, description: str, tags: str,
                          duration_seconds: int, published_at: str, thumbnail_url: str) -> None:
    _exec(
        "INSERT OR REPLACE INTO video_metadata_cache "
        "(video_id, title, description, tags, duration_seconds, published_at, thumbnail_url, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (video_id, title, description, tags, duration_seconds, published_at, thumbnail_url), commit=True,
    )


def get_video_metadata(video_id: str) -> dict | None:
    row = _exec(
        "SELECT * FROM video_metadata_cache WHERE video_id = ?",
        (video_id,),
    ).fetchone()
    return dict(row) if row else None


def get_all_video_metadata() -> list[dict]:
    rows = _exec("SELECT * FROM video_metadata_cache ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


def upsert_scheduled_video(video_id: str, title: str, scheduled_time: str, privacy_status: str) -> None:
    _exec(
        "INSERT OR REPLACE INTO scheduled_videos "
        "(video_id, title, scheduled_time, privacy_status, last_checked) "
        "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (video_id, title, scheduled_time, privacy_status), commit=True,
    )


def get_scheduled_videos() -> list[dict]:
    rows = _exec(
        "SELECT * FROM scheduled_videos WHERE scheduled_time >= datetime('now') "
        "ORDER BY scheduled_time ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def clear_old_scheduled() -> None:
    _exec(
        "DELETE FROM scheduled_videos WHERE scheduled_time < datetime('now', '-7 days')",
        commit=True,
    )
