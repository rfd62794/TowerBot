"""Game metrics tool — per-game deep dive with Steam + YouTube data."""

import difflib
import hashlib
import json
from datetime import datetime, timedelta
from tools.api.steam_api import get_game_library, resolve_appid_from_library
from tools.api.steamspy_api import get_app_details
from tools.api.itad_api import lookup_game, get_prices
from tools.api.steam_catalog_api import get_full_catalog, fuzzy_match_catalog
from tools.api.youtube_api import search_youtube, get_video_statistics
from core.db import cache_tool_result, get_cached_tool_result, record_game_day, get_game_history


def resolve_appid(game_name: str) -> dict | None:
    """
    Resolve game name to AppID with fuzzy matching.

    Priority:
    1. Exact match in owned library
    2. Fuzzy match in owned library
    3. Exact match in Steam catalog
    4. Fuzzy match in Steam catalog

    Returns:
        {"appid": int, "name": str, "source": "owned"|"catalog"} or None
    """
    params_hash = hashlib.md5(game_name.encode()).hexdigest()
    cached = get_cached_tool_result("resolve_appid", params_hash)
    if cached:
        return cached

    # Step 1: Search owned library first
    library_result = get_game_library()
    if "error" not in library_result:
        owned = library_result["raw"]
        for game in owned:
            if game_name.lower() in game["name"].lower():
                result = {"appid": game["appid"], "name": game["name"], "source": "owned"}
                cache_tool_result("resolve_appid", params_hash, result, ttl_hours=24*7)
                return result

        # Step 2: Fuzzy match owned library
        names = [g["name"] for g in owned]
        matches = difflib.get_close_matches(game_name, names, n=1, cutoff=0.6)
        if matches:
            match = next(g for g in owned if g["name"] == matches[0])
            result = {"appid": match["appid"], "name": match["name"], "source": "owned"}
            cache_tool_result("resolve_appid", params_hash, result, ttl_hours=24*7)
            return result

    # Step 3: Full Steam catalog search
    catalog_result = get_full_catalog()
    if "error" not in catalog_result:
        catalog = catalog_result["raw"]
        for app in catalog:
            if game_name.lower() in app.get("name", "").lower():
                result = {"appid": app["appid"], "name": app["name"], "source": "catalog"}
                cache_tool_result("resolve_appid", params_hash, result, ttl_hours=24*7)
                return result

        # Step 4: Fuzzy match catalog
        catalog_names = [app.get("name", "") for app in catalog]
        matches = difflib.get_close_matches(game_name, catalog_names, n=1, cutoff=0.7)
        if matches:
            match = next(app for app in catalog if app.get("name") == matches[0])
            result = {"appid": match["appid"], "name": match["name"], "source": "catalog"}
            cache_tool_result("resolve_appid", params_hash, result, ttl_hours=24*7)
            return result

    return None


def get_steamspy_info(appid: int) -> dict:
    """Get SteamSpy data for a specific game."""
    params_hash = hashlib.md5(str(appid).encode()).hexdigest()
    cached = get_cached_tool_result("get_steamspy_info", params_hash)
    if cached:
        return cached

    result = get_app_details(appid)
    if "error" in result:
        return {}
    
    data = result["raw"]
    result_data = {
        "owners": data.get("owners", "0 .. 0"),
        "players_forever": data.get("players_forever", 0),
        "players_2weeks": data.get("players_2weeks", 0),
        "positive_reviews": data.get("positive", 0),
        "negative_reviews": data.get("negative", 0),
    }
    cache_tool_result("get_steamspy_info", params_hash, result_data, ttl_hours=24)
    return result_data


def get_youtube_coverage(game_name: str, days: int = 30) -> dict:
    """Get YouTube coverage data for a game."""
    params_hash = hashlib.md5(f"{game_name}_{days}".encode()).hexdigest()
    cached = get_cached_tool_result("get_youtube_coverage", params_hash)
    if cached:
        return cached

    try:
        api_response = search_youtube(f"{game_name} gameplay", days, max_results=5)
        if "error" in api_response:
            result = {"recent_count": 0, "top_views": 0, "gap_signal": "none"}
            cache_tool_result("get_youtube_coverage", params_hash, result, ttl_hours=24)
            return result

        response = api_response["raw"]
        video_ids = [item["id"]["videoId"] for item in response.get("items", [])]

        if not video_ids:
            result = {"recent_count": 0, "top_views": 0, "gap_signal": "none"}
            cache_tool_result("get_youtube_coverage", params_hash, result, ttl_hours=24)
            return result

        # Get video statistics
        stats_response = get_video_statistics(video_ids)
        if "error" in stats_response:
            result = {"recent_count": len(video_ids), "top_views": 0, "gap_signal": "none"}
            cache_tool_result("get_youtube_coverage", params_hash, result, ttl_hours=24)
            return result

        stats = stats_response["raw"]
        view_counts = []
        for video in stats.get("items", []):
            views = int(video["statistics"].get("viewCount", 0))
            view_counts.append(views)

        if view_counts:
            recent_count = len(view_counts)
            top_views = max(view_counts)

            # Gap signal logic
            if recent_count == 0:
                gap_signal = "none"
            elif recent_count < 5:
                gap_signal = "low"
            elif recent_count < 20:
                gap_signal = "medium"
            else:
                gap_signal = "high"

            result = {
                "recent_count": recent_count,
                "top_views": top_views,
                "gap_signal": gap_signal,
            }
            cache_tool_result("get_youtube_coverage", params_hash, result, ttl_hours=24)
            return result
        result = {"recent_count": 0, "top_views": 0, "gap_signal": "none"}
        cache_tool_result("get_youtube_coverage", params_hash, result, ttl_hours=24)
        return result
    except Exception:
        result = {"recent_count": 0, "top_views": 0, "gap_signal": "none"}
        cache_tool_result("get_youtube_coverage", params_hash, result, ttl_hours=24)
        return result


def get_game_metrics(game_name: str) -> dict:
    """
    Get detailed metrics for a specific game by name.

    Automatically resolves AppID from game name using fuzzy matching.
    Combines SteamSpy market data, your personal playtime, and YouTube
    coverage to provide a comprehensive view of a game's content potential.

    Args:
        game_name: Name of the game (e.g. "Raccoin", "Duckov")

    Returns:
        Dict with game metrics, playtime, player counts, YouTube coverage,
        content gap signal, and verdict
    """
    params_hash = hashlib.md5(game_name.encode()).hexdigest()
    cached = get_cached_tool_result("get_game_metrics", params_hash)
    if cached:
        return cached

    # Resolve AppID
    resolved = resolve_appid(game_name)
    if not resolved:
        return {"error": f"Game not found: {game_name}"}

    appid = resolved["appid"]
    name = resolved["name"]

    # Get your playtime
    library_result = get_game_library()
    your_playtime = 0.0
    if "error" not in library_result:
        owned = library_result["raw"]
        for game in owned:
            if game["appid"] == appid:
                your_playtime = game["playtime_hours"]
                break

    # Get SteamSpy data
    steamspy_data = get_steamspy_info(appid)

    # Get YouTube coverage
    yt_data = get_youtube_coverage(name)

    # Calculate review score
    positive = steamspy_data.get("positive_reviews", 0)
    negative = steamspy_data.get("negative_reviews", 0)
    total = positive + negative
    review_score = (positive / total * 100.0) if total > 0 else None

    # Verdict logic
    gap = yt_data.get("gap_signal", "none")
    if gap == "none" and your_playtime > 5:
        verdict = "Strong opportunity — underserved content, you know the game."
    elif gap == "low" and your_playtime > 5:
        verdict = "Good opportunity — limited competition."
    elif gap == "high":
        verdict = "Saturated — hard to surface organically."
    elif your_playtime < 1:
        verdict = "Insufficient playtime to speak to this."
    else:
        verdict = "Moderate opportunity — worth considering."

    result = {
        "name": name,
        "appid": appid,
        "your_playtime_hours": your_playtime,
        "steam_owners": steamspy_data.get("owners", "0 .. 0"),
        "players_2weeks": steamspy_data.get("players_2weeks", 0),
        "review_score": review_score,
        "youtube_recent_uploads": yt_data.get("recent_count", 0),
        "youtube_top_views": yt_data.get("top_views", 0),
        "content_gap": gap,
        "verdict": verdict,
    }

    # Add trend data from history if available
    history = get_game_history(appid, days=14)
    if len(history) >= 7:
        # Prior week is the first 7 days (oldest)
        prior_week = history[:7]
        prior_players = sum(h["players_2weeks"] for h in prior_week) / len(prior_week)
        
        # Calculate change percentage
        current_players = steamspy_data.get("players_2weeks", 0)
        players_change = 0
        if prior_players > 0:
            players_change = ((current_players - prior_players) / prior_players) * 100
        
        result["players_prev_week"] = round(prior_players, 0)
        result["players_change_pct"] = round(players_change, 1)
        result["history_weeks_available"] = len(history)
    else:
        result["history_weeks_available"] = len(history)

    # Cache result
    cache_tool_result("get_game_metrics", params_hash, result, ttl_hours=24)

    # Record to game history if valid
    if "error" not in result:
        # Parse owners range for history
        owners_str = steamspy_data.get("owners", "0 .. 0")
        try:
            owners_low = int(owners_str.split("..")[0].replace(",", "").strip())
            owners_high = int(owners_str.split("..")[1].replace(",", "").strip())
        except (ValueError, IndexError, AttributeError):
            owners_low = 0
            owners_high = 0

        record_game_day(
            appid,
            datetime.now().strftime("%Y-%m-%d"),
            steamspy_data.get("players_2weeks", 0),
            owners_low,
            owners_high,
            0,  # price_usd - fetched separately in get_sale_info
            False,  # on_sale - fetched separately
        )

    return result


def get_installed_games() -> dict:
    """
    Get currently installed games from Steam library.

    Returns games that are installed on the local machine,
    sorted by last played time (most recent first).

    Returns:
        Dict with count and list of installed games
    """
    params_hash = hashlib.md5("installed_games".encode()).hexdigest()
    cached = get_cached_tool_result("get_installed_games", params_hash)
    if cached:
        return cached

    library_result = get_game_library()
    if "error" in library_result:
        result = {"count": 0, "games": []}
        cache_tool_result("get_installed_games", params_hash, result, ttl_hours=1)
        return result

    owned = library_result["raw"]

    # Filter to installed games (Steam API doesn't provide this directly,
    # so we return all owned games with playtime > 0 as a proxy for "installed")
    # This is a limitation of the Steam Web API - it doesn't expose installation status
    installed = [g for g in owned if g["playtime_hours"] > 0]

    # Sort by playtime (proxy for recency since last_played isn't always available)
    installed.sort(key=lambda x: x["playtime_hours"], reverse=True)

    result = {
        "count": len(installed),
        "games": [
            {
                "name": g["name"],
                "appid": g["appid"],
                "playtime_hours": g["playtime_hours"],
            }
            for g in installed
        ],
    }
    cache_tool_result("get_installed_games", params_hash, result, ttl_hours=1)
    return result


def get_sale_info(game_names: list[str]) -> dict:
    """
    Check current sale prices and historical lows for games via IsThereAnyDeal.

    Args:
        game_names: List of game names to check

    Returns:
        Dict with per-game sale information
    """
    params_hash = hashlib.md5("_".join(sorted(game_names)).encode()).hexdigest()
    cached = get_cached_tool_result("get_sale_info", params_hash)
    if cached:
        return cached

    results = {}
    game_ids = []

    # Step 1: Lookup all game IDs via search
    for game_name in game_names:
        lookup_result = lookup_game(game_name)
        if "error" in lookup_result:
            results[game_name] = {"error": lookup_result["error"]}
            continue
        
        search_data = lookup_result["raw"]
        if search_data and isinstance(search_data, list) and len(search_data) > 0:
            game_id = search_data[0].get("id")
            if game_id:
                game_ids.append(game_id)
                results[game_name] = {"id": game_id}
            else:
                results[game_name] = {"error": "not found"}
        else:
            results[game_name] = {"error": "not found"}

    # Step 2: Get prices for all found games (batch request)
    if game_ids:
        prices_result = get_prices(game_ids, country="US")
        if "error" in prices_result:
            for game_name in results:
                if "error" not in results[game_name]:
                    results[game_name] = {"error": prices_result["error"]}
            result = {"games": results}
            cache_tool_result("get_sale_info", params_hash, result, ttl_hours=1)
            return result
        
        prices_data = prices_result["raw"]

        # Map game IDs to price data
        price_map = {}
        for price_info in prices_data:
            game_id = price_info.get("id")
            if game_id:
                price_map[game_id] = price_info

        # Merge price data into results
        for game_name, data in results.items():
            if "error" in data:
                continue
            game_id = data.get("id")
            if game_id in price_map:
                price_info = price_map[game_id]
                deals = price_info.get("deals", [])
                history_low = price_info.get("historyLow", {})

                # Find best current deal
                best_deal = None
                for deal in deals:
                    if deal.get("price") and deal.get("cut"):
                        if best_deal is None or deal["cut"] > best_deal["cut"]:
                            best_deal = deal

                if best_deal:
                    results[game_name] = {
                        "current_price": best_deal.get("price", {}).get("amount", 0.0),
                        "current_discount_pct": best_deal.get("cut", 0),
                        "historical_low": history_low.get("price", {}).get("amount", 0.0),
                        "on_sale": best_deal.get("cut", 0) > 0,
                        "store_name": best_deal.get("shop", {}).get("name", "Unknown"),
                        "store_url": best_deal.get("url", ""),
                    }
                else:
                    results[game_name] = {
                        "current_price": history_low.get("price", {}).get("amount", 0.0),
                        "current_discount_pct": 0,
                        "historical_low": history_low.get("price", {}).get("amount", 0.0),
                        "on_sale": False,
                        "store_name": "Steam",
                        "store_url": "",
                    }
            else:
                results[game_name] = {"error": "no price data"}

    result = {"games": results}
    cache_tool_result("get_sale_info", params_hash, result, ttl_hours=1)

    # Record price to game history for games with valid data
    for game_name, data in results.items():
        if "error" not in data and "current_price" in data:
            # Resolve appid for this game
            resolved = resolve_appid(game_name)
            if resolved:
                appid = resolved["appid"]
                current_price = data.get("current_price", 0.0)
                on_sale = data.get("on_sale", False)
                
                # Get existing history to preserve other fields
                existing_history = get_game_history(appid, days=1)
                if existing_history:
                    existing = existing_history[0]
                    record_game_day(
                        appid,
                        datetime.now().strftime("%Y-%m-%d"),
                        existing.get("players_2weeks", 0),
                        existing.get("owners_low", 0),
                        existing.get("owners_high", 0),
                        current_price,
                        on_sale,
                    )
                else:
                    record_game_day(
                        appid,
                        datetime.now().strftime("%Y-%m-%d"),
                        0, 0, 0, current_price, on_sale,
                    )

    return result
