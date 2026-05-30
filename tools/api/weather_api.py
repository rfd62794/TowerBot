"""Weather API client — Open-Meteo, no key required."""

import requests

LATITUDE = 26.71  # South Florida
LONGITUDE = -80.05

WEATHER_CODE_MAP = {
    0: "Clear skies",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def get_current_weather() -> dict:
    """
    Get current weather for South Florida.

    Returns:
        Dict with temperature, condition, wind, precipitation, and staleness metadata
    """
    from core.cache import cache

    def _live() -> dict:
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "current": "temperature_2m,weather_code,wind_speed_10m,precipitation",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            current = data.get("current", {})
            weather_code = current.get("weather_code", 0)

            return {
                "temp_f": current.get("temperature_2m", 0),
                "condition": WEATHER_CODE_MAP.get(weather_code, "Unknown"),
                "wind_mph": current.get("wind_speed_10m", 0),
                "precipitation_mm": current.get("precipitation", 0),
            }
        except Exception as e:
            return {"error": str(e)}

    result = cache.call("weather", cache.hash(), _live, stale_ok=True)

    # Add stale_notice to result
    notice = cache.stale_notice(result)
    result["stale_notice"] = notice

    return result
