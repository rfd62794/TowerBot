"""Channel-level YouTube tools."""

import hashlib
import json
from datetime import datetime, timedelta
from core.db import cache_tool_result, get_cached_tool_result, get_channel_history
from tools.api.youtube_api import (
    query_channel_report,
    query_daily_views,
    query_demographics,
    query_device_types,
    query_geography,
)


def _hash_params(params: dict) -> str:
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()


def get_channel_summary(days: int = 7) -> dict:
    """
    Get YouTube channel performance for last N days.

    Args:
        days: Number of days to look back (default: 7)

    Returns:
        Dict with views, watch_time, subscribers, and date range.
        Includes trend data if prior week history exists.
    """
    params = {"days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_channel_summary", params_hash)
    if cached:
        return cached

    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_channel_report(start, end, "views,estimatedMinutesWatched,subscribersGained")
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [[0, 0, 0]])
        if not rows:
            return {"error": "No data returned from YouTube Analytics"}

        row = rows[0]
        result = {
            "views": int(row[0]),
            "watch_time_minutes": float(row[1]),
            "subscribers_gained": int(row[2]),
            "start_date": start,
            "end_date": end,
            "period_days": days,
        }

        history = get_channel_history(days=14)
        if len(history) >= 7:
            prior_week = history[:7]
            prior_views = sum(h["views"] for h in prior_week)
            prior_subs = sum(h["subscribers_gained"] for h in prior_week)

            views_change = 0
            if prior_views > 0:
                views_change = ((result["views"] - prior_views) / prior_views) * 100

            subs_change = 0
            if prior_subs > 0:
                subs_change = ((result["subscribers_gained"] - prior_subs) / prior_subs) * 100

            result["trend"] = {
                "views_prev_week": prior_views,
                "views_change_pct": round(views_change, 1),
                "subs_prev_week": prior_subs,
                "subs_change_pct": round(subs_change, 1),
            }
            result["history_days_available"] = len(history)
        else:
            result["history_days_available"] = len(history)

        cache_tool_result("get_channel_summary", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_daily_views(days: int = 28) -> dict:
    """
    Get daily views time series.

    Args:
        days: Number of days to look back (default: 28)

    Returns:
        Dict with daily views, watch time, and subscriber gains
    """
    params = {"days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_daily_views", params_hash)
    if cached:
        return cached

    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_daily_views(start, end)
        if "error" in api_response:
            return api_response

        response = api_response.get("raw")
        if response is None:
            return {"error": "No data available", "days": []}

        rows = response.get("rows", [])

        days_data = []
        for row in rows:
            days_data.append({
                "date": row[0],
                "views": int(row[1]),
                "watch_time_minutes": float(row[2]),
                "subs": int(row[3]) if len(row) > 3 else 0,
            })

        result = {
            "days": days_data,
            "period_days": days,
        }

        cache_tool_result("get_daily_views", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_geographic_breakdown(days: int = 28) -> dict:
    """
    Get geographic breakdown by country.

    Args:
        days: Number of days to look back (default: 28)

    Returns:
        Dict with top countries by views
    """
    params = {"days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_geographic_breakdown", params_hash)
    if cached:
        return cached

    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_geography(start, end)
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [])

        countries = []
        total_views = sum(int(row[1]) for row in rows)

        for row in rows:
            country = row[0]
            views = int(row[1])
            watch_time = float(row[2])

            countries.append({
                "country": country,
                "views": views,
                "watch_time_minutes": watch_time,
                "pct": views / total_views * 100 if total_views > 0 else 0.0,
            })

        result = {
            "countries": countries,
            "period_days": days,
        }

        cache_tool_result("get_geographic_breakdown", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_audience_demographics(days: int = 28) -> dict:
    """
    Get audience demographics by age and gender.

    Args:
        days: Number of days to look back (default: 28)

    Returns:
        Dict with age groups and gender breakdown
    """
    params = {"days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_audience_demographics", params_hash)
    if cached:
        return cached

    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_demographics(start, end)
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [])

        age_groups = {}
        gender = {}

        for row in rows:
            age_group = row[0]
            gender_type = row[1]
            viewer_pct = float(row[2])

            if age_group not in age_groups:
                age_groups[age_group] = 0.0
            age_groups[age_group] += viewer_pct

            if gender_type not in gender:
                gender[gender_type] = 0.0
            gender[gender_type] += viewer_pct

        result = {
            "age_groups": age_groups,
            "gender": gender,
            "period_days": days,
        }

        cache_tool_result("get_audience_demographics", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_device_breakdown(days: int = 28) -> dict:
    """
    Get device type breakdown.

    Args:
        days: Number of days to look back (default: 28)

    Returns:
        Dict with device breakdown by views and percentage
    """
    params = {"days": days}
    params_hash = _hash_params(params)
    cached = get_cached_tool_result("get_device_breakdown", params_hash)
    if cached:
        return cached

    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        api_response = query_device_types(start, end)
        if "error" in api_response:
            return api_response

        response = api_response["raw"]
        rows = response.get("rows", [])

        devices = {}
        total_views = 0

        for row in rows:
            device_type = row[0]
            views = int(row[1])
            watch_time = float(row[2])

            devices[device_type] = {
                "views": views,
                "watch_time_minutes": watch_time,
            }
            total_views += views

        for device_type in devices:
            devices[device_type]["pct"] = devices[device_type]["views"] / total_views * 100 if total_views > 0 else 0.0

        result = {
            "devices": devices,
            "period_days": days,
        }

        cache_tool_result("get_device_breakdown", params_hash, result, ttl_hours=6)
        return result
    except Exception as e:
        return {"error": str(e)}
