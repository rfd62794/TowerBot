"""Channel-level YouTube tools."""

import hashlib
import json
from datetime import datetime, timedelta
from infra.db import get_channel_history
from tools._tool import BaseTool
from tools.api.youtube_api import (
    query_channel_report,
    query_daily_views,
    query_demographics,
    query_device_types,
    query_geography,
)


class ChannelTools(BaseTool):
    """YouTube channel-level tools with BaseTool pattern."""

    def get_channel_summary_range(self, start_date: str, end_date: str) -> dict:
        """
        Get YouTube channel performance for a specific date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Dict with views, watch_time, subscribers, and date range.
        """
        try:
            api_response = query_channel_report(start_date, end_date, "views,estimatedMinutesWatched,subscribersGained")
            if "error" in api_response:
                return self.error(api_response["error"], code="api_failed")

            response = api_response["raw"]
            rows = response.get("rows", [[0, 0, 0]])
            if not rows:
                return self.error("No data returned from YouTube Analytics", code="no_data")

            row = rows[0]
            return self.success({
                "views": int(row[0]),
                "watch_time_minutes": float(row[1]),
                "subscribers_gained": int(row[2]),
                "start_date": start_date,
                "end_date": end_date,
            })
        except Exception as e:
            return self.error(str(e), code="exception")

    def get_channel_summary(self, days: int = 7) -> dict:
        """
        Get YouTube channel performance for last N days.

        Args:
            days: Number of days to look back (default: 7)

        Returns:
            Dict with views, watch_time, subscribers, and date range.
            Includes trend data if prior week history exists.
        """
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            api_response = query_channel_report(start, end, "views,estimatedMinutesWatched,subscribersGained")
            if "error" in api_response:
                return self.error(api_response["error"], code="api_failed")

            response = api_response["raw"]
            rows = response.get("rows", [[0, 0, 0]])
            if not rows:
                return self.error("No data returned from YouTube Analytics", code="no_data")

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

            return self.success(result, stale_result=api_response)
        except Exception as e:
            return self.error(str(e), code="exception")

    def get_daily_views(self, days: int = 28) -> dict:
        """
        Get daily views time series.

        Args:
            days: Number of days to look back (default: 28)

        Returns:
            Dict with daily views, watch time, and subscriber gains
        """
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            api_response = query_daily_views(start, end)
            if "error" in api_response:
                return self.error(api_response["error"], code="api_failed")

            response = api_response.get("raw")
            if response is None:
                return self.error("No data available", code="no_data")

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

            return self.success(result, stale_result=api_response)
        except Exception as e:
            return self.error(str(e), code="exception")

    def get_geographic_breakdown(self, days: int = 28) -> dict:
        """
        Get geographic breakdown by country.

        Args:
            days: Number of days to look back (default: 28)

        Returns:
            Dict with top countries by views
        """
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            api_response = query_geography(start, end)
            if "error" in api_response:
                return self.error(api_response["error"], code="api_failed")

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

            return self.success(result, stale_result=api_response)
        except Exception as e:
            return self.error(str(e), code="exception")

    def get_audience_demographics(self, days: int = 28) -> dict:
        """
        Get audience demographics by age and gender.

        Args:
            days: Number of days to look back (default: 28)

        Returns:
            Dict with age groups and gender breakdown
        """
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            api_response = query_demographics(start, end)
            if "error" in api_response:
                return self.error(api_response["error"], code="api_failed")

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

            return self.success(result, stale_result=api_response)
        except Exception as e:
            return self.error(str(e), code="exception")

    def get_device_breakdown(self, days: int = 28) -> dict:
        """
        Get device type breakdown.

        Args:
            days: Number of days to look back (default: 28)

        Returns:
            Dict with device breakdown by views and percentage
        """
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            api_response = query_device_types(start, end)
            if "error" in api_response:
                return self.error(api_response["error"], code="api_failed")

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

            return self.success(result, stale_result=api_response)
        except Exception as e:
            return self.error(str(e), code="exception")


# Module-level instance
_channel_tools = ChannelTools()


# Backwards compat module-level functions
def get_channel_summary_range(start_date: str, end_date: str) -> dict:
    return _channel_tools.get_channel_summary_range(start_date, end_date)


def get_channel_summary(days: int = 7) -> dict:
    return _channel_tools.get_channel_summary(days)


def get_daily_views(days: int = 28) -> dict:
    return _channel_tools.get_daily_views(days)


def get_geographic_breakdown(days: int = 28) -> dict:
    return _channel_tools.get_geographic_breakdown(days)


def get_audience_demographics(days: int = 28) -> dict:
    return _channel_tools.get_audience_demographics(days)


def get_device_breakdown(days: int = 28) -> dict:
    return _channel_tools.get_device_breakdown(days)

