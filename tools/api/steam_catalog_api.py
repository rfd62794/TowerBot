"""Steam catalog API client — raw API calls only."""

import os
import json
import requests
from datetime import datetime
from pathlib import Path

STEAM_API = "https://api.steampowered.com"
STEAM_CATALOG_CACHE = Path("config/steam_catalog.json")


def get_full_catalog() -> dict:
    """Get full Steam catalog with caching."""
    # Check cache (valid for 7 days)
    if STEAM_CATALOG_CACHE.exists():
        try:
            with open(STEAM_CATALOG_CACHE, "r") as f:
                cache_data = json.load(f)
                cache_time = datetime.fromisoformat(cache_data.get("timestamp", "1970-01-01"))
                if (datetime.now() - cache_time).total_seconds() < 604800:  # 7 days
                    return {"raw": cache_data.get("apps", [])}
        except (IOError, json.JSONDecodeError):
            pass

    # Fetch fresh catalog
    try:
        response = requests.get(
            f"{STEAM_API}/ISteamApps/GetAppList/v2/",
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        apps = data.get("applist", {}).get("apps", [])

        # Cache with timestamp
        STEAM_CATALOG_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(STEAM_CATALOG_CACHE, "w") as f:
            json.dump({"timestamp": datetime.now().isoformat(), "apps": apps}, f)

        return {"raw": apps}
    except Exception as e:
        return {"error": str(e)}


def fuzzy_match_catalog(name: str) -> dict:
    """Fuzzy match game name in Steam catalog."""
    import difflib
    
    result = get_full_catalog()
    if "error" in result:
        return result
    
    catalog = result["raw"]
    catalog_names = [app.get("name", "") for app in catalog]
    matches = difflib.get_close_matches(name, catalog_names, n=1, cutoff=0.7)
    
    if matches:
        match = next(app for app in catalog if app.get("name") == matches[0])
        return {"raw": {"appid": match["appid"], "name": match["name"]}}
    
    return {"error": "No match found in catalog"}
