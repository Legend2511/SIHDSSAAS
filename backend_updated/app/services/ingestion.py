"""
WeatherGPT — Data Ingestion Service

Three data sources:
  1. get_openweather(lat, lon)   — live OpenWeatherMap API (free tier)
  2. get_imd_mock(district)      — realistic mock IMD bulletins
  3. get_mosdac_mock(region)     — realistic mock MOSDAC satellite data

All return WeatherSnapshot. The single function to change when real credentials
arrive is clearly marked per source.

Also provides get_weather_for_location(location_str) which geocodes a location
name and returns the best available WeatherSnapshot.
"""

import hashlib
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from app.core.config import settings
from app.schemas.weather import AlertLevel, WeatherSnapshot

# IST timezone offset
IST = timezone(timedelta(hours=5, minutes=30))


# =============================================================================
# HELPER: Derive alert level from weather conditions
# =============================================================================

def _derive_alert_level(
    temp_c: float,
    rainfall_mm: float,
    wind_kmph: float,
    description: str = "",
) -> tuple[AlertLevel, Optional[str]]:
    """
    Deterministic alert level derivation based on IMD-like thresholds.
    Returns (alert_level, headline_or_None).

    Thresholds (simplified from IMD guidelines):
    - Red:    rainfall >= 204mm/24h OR wind >= 170 km/h OR temp >= 47°C OR temp <= -10°C
    - Orange: rainfall >= 115mm/24h OR wind >= 100 km/h OR temp >= 44°C OR temp <= -5°C
    - Yellow: rainfall >= 64mm/24h  OR wind >= 60 km/h  OR temp >= 40°C OR temp <= 0°C
    """
    # Scale per-hour rainfall to approximate 24h equivalent for threshold comparison
    # OWM gives 1h or 3h rainfall; mocks give snapshot values
    rain_24h_estimate = rainfall_mm * 8  # rough scaling from 3h to 24h

    if rain_24h_estimate >= 204 or wind_kmph >= 170 or temp_c >= 47 or temp_c <= -10:
        return AlertLevel.RED, "Extremely severe weather conditions — take immediate action"
    elif rain_24h_estimate >= 115 or wind_kmph >= 100 or temp_c >= 44 or temp_c <= -5:
        return AlertLevel.ORANGE, "Severe weather expected — be prepared for disruptions"
    elif rain_24h_estimate >= 64 or wind_kmph >= 60 or temp_c >= 40 or temp_c <= 0:
        return AlertLevel.YELLOW, "Adverse weather possible — stay alert and updated"
    else:
        return AlertLevel.GREEN, None


# =============================================================================
# SOURCE 1: OpenWeatherMap (LIVE)
# =============================================================================

# ──────────────────────────────────────────────────────────────────────────
# To switch to real OWM: just set OPENWEATHER_API_KEY in .env
# This is the ONLY function that calls the OWM API.
# ──────────────────────────────────────────────────────────────────────────

async def get_openweather(lat: float, lon: float) -> Optional[WeatherSnapshot]:
    """
    Fetch current weather from OpenWeatherMap free API.
    Returns None if API key is missing or request fails.
    """
    if not settings.openweather_api_key:
        return None

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": settings.openweather_api_key,
        "units": "metric",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        # Extract fields
        temp_c = data["main"]["temp"]
        feels_like = data["main"].get("feels_like")
        humidity = data["main"]["humidity"]
        wind_speed_ms = data["wind"]["speed"]
        wind_kmph = round(wind_speed_ms * 3.6, 1)
        wind_deg = data["wind"].get("deg", 0)

        # Wind direction from degrees
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        wind_dir = directions[int((wind_deg + 22.5) / 45) % 8]

        # Rainfall (may be absent)
        rainfall_mm = 0.0
        if "rain" in data:
            rainfall_mm = data["rain"].get("1h", data["rain"].get("3h", 0.0))

        # Other fields
        visibility_km = data.get("visibility", 10000) / 1000
        pressure = data["main"].get("pressure")
        clouds = data.get("clouds", {}).get("all", 0)
        description = data["weather"][0]["description"] if data.get("weather") else ""
        location_name = data.get("name", f"{lat},{lon}")

        alert_level, headline = _derive_alert_level(temp_c, rainfall_mm, wind_kmph, description)

        return WeatherSnapshot(
            location=location_name,
            lat=lat,
            lon=lon,
            timestamp=datetime.fromtimestamp(data["dt"], tz=timezone.utc),
            temp_c=temp_c,
            feels_like_c=feels_like,
            rainfall_mm=rainfall_mm,
            wind_kmph=wind_kmph,
            wind_direction=wind_dir,
            humidity_pct=humidity,
            visibility_km=visibility_km,
            pressure_hpa=pressure,
            cloud_cover_pct=clouds,
            alert_level=alert_level,
            alert_headline=headline,
            description=description.capitalize(),
            source="openweathermap_live",
        )
    except Exception as e:
        print(f"⚠️  OpenWeatherMap API error: {e}")
        return None


# =============================================================================
# GEOCODING: Location name → lat/lon
# =============================================================================

# Well-known Indian cities/districts for fast geocoding without API call
_GEOCODE_CACHE: dict[str, tuple[float, float]] = {
    "mumbai": (19.076, 72.8777),
    "delhi": (28.6139, 77.209),
    "new delhi": (28.6139, 77.209),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "hyderabad": (17.385, 78.4867),
    "pune": (18.5204, 73.8567),
    "shimla": (31.1048, 77.1734),
    "jaipur": (26.9124, 75.7873),
    "ahmedabad": (23.0225, 72.5714),
    "lucknow": (26.8467, 80.9462),
    "bhopal": (23.2599, 77.4126),
    "patna": (25.6093, 85.1376),
    "visakhapatnam": (17.6868, 83.2185),
    "vizag": (17.6868, 83.2185),
    "kochi": (9.9312, 76.2673),
    "guwahati": (26.1445, 91.7362),
    "chandigarh": (30.7333, 76.7794),
    "thiruvananthapuram": (8.5241, 76.9366),
    "srinagar": (34.0837, 74.7973),
    "dehradun": (30.3165, 78.0322),
    "ranchi": (23.3441, 85.3096),
    "bhubaneswar": (20.2961, 85.8245),
    "nagpur": (21.1458, 79.0882),
    "coimbatore": (11.0168, 76.9558),
    "varanasi": (25.3176, 82.9739),
    "agra": (27.1767, 78.0081),
    "indore": (22.7196, 75.8577),
    "mangalore": (12.9141, 74.856),
    "surat": (21.1702, 72.8311),
    "madurai": (9.9252, 78.1198),
    "puri": (19.8135, 85.8312),
    "darjeeling": (27.0360, 88.2627),
    "gangtok": (27.3389, 88.6065),
    "imphal": (24.817, 93.9368),
    "aizawl": (23.7271, 92.7176),
}


async def geocode_location(location_str: str) -> tuple[float, float]:
    """
    Geocode a location string to (lat, lon).
    Uses local cache first, then OWM Geocoding API, then a default.
    """
    # Clean input
    clean = location_str.lower().strip()
    # Try matching city name from the string (handles "Shimla, Himachal Pradesh")
    for city, coords in _GEOCODE_CACHE.items():
        if city in clean:
            return coords

    # Try OWM Geocoding API
    if settings.openweather_api_key:
        try:
            url = "https://api.openweathermap.org/geo/1.0/direct"
            params = {"q": location_str, "limit": 1, "appid": settings.openweather_api_key}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                if data:
                    return (data[0]["lat"], data[0]["lon"])
        except Exception:
            pass

    # Default: New Delhi
    return (28.6139, 77.209)


# =============================================================================
# SOURCE 2: IMD Mock Feed
# =============================================================================

# ──────────────────────────────────────────────────────────────────────────
# To switch to real IMD: replace the body of this function with an API call
# to api.imd.gov.in once nodal officer approval is granted.
# This is the ONLY function that needs to change.
# ──────────────────────────────────────────────────────────────────────────

# 10 varied mock scenarios covering different alert levels
_IMD_MOCK_SCENARIOS = [
    {
        "name": "clear_day",
        "temp_c": 32.5, "rainfall_mm": 0.0, "wind_kmph": 12.0, "humidity_pct": 45.0,
        "description": "Clear sky with good visibility", "visibility_km": 10.0,
        "pressure_hpa": 1013.0, "cloud_cover_pct": 10.0,
    },
    {
        "name": "heavy_monsoon",
        "temp_c": 26.0, "rainfall_mm": 45.0, "wind_kmph": 35.0, "humidity_pct": 95.0,
        "description": "Heavy monsoon rainfall with thunderstorms expected",
        "visibility_km": 2.0, "pressure_hpa": 1002.0, "cloud_cover_pct": 95.0,
    },
    {
        "name": "cyclone_watch",
        "temp_c": 28.0, "rainfall_mm": 80.0, "wind_kmph": 120.0, "humidity_pct": 92.0,
        "description": "Cyclonic storm approaching — very heavy rainfall and strong winds",
        "visibility_km": 1.5, "pressure_hpa": 985.0, "cloud_cover_pct": 100.0,
    },
    {
        "name": "heatwave",
        "temp_c": 46.5, "rainfall_mm": 0.0, "wind_kmph": 18.0, "humidity_pct": 15.0,
        "description": "Severe heatwave — temperatures significantly above normal",
        "visibility_km": 8.0, "pressure_hpa": 1008.0, "cloud_cover_pct": 5.0,
    },
    {
        "name": "frost_warning",
        "temp_c": -2.0, "rainfall_mm": 0.0, "wind_kmph": 8.0, "humidity_pct": 75.0,
        "description": "Ground frost expected in early morning hours",
        "visibility_km": 3.0, "pressure_hpa": 1025.0, "cloud_cover_pct": 30.0,
    },
    {
        "name": "thunderstorm",
        "temp_c": 30.0, "rainfall_mm": 25.0, "wind_kmph": 55.0, "humidity_pct": 80.0,
        "description": "Thunderstorm with lightning and gusty winds",
        "visibility_km": 4.0, "pressure_hpa": 1006.0, "cloud_cover_pct": 85.0,
    },
    {
        "name": "fog",
        "temp_c": 8.0, "rainfall_mm": 0.0, "wind_kmph": 5.0, "humidity_pct": 98.0,
        "description": "Dense fog reducing visibility significantly",
        "visibility_km": 0.2, "pressure_hpa": 1020.0, "cloud_cover_pct": 100.0,
    },
    {
        "name": "dust_storm",
        "temp_c": 42.0, "rainfall_mm": 0.0, "wind_kmph": 75.0, "humidity_pct": 10.0,
        "description": "Dust storm with strong winds and very low visibility",
        "visibility_km": 0.5, "pressure_hpa": 1004.0, "cloud_cover_pct": 40.0,
    },
    {
        "name": "very_heavy_rain",
        "temp_c": 24.0, "rainfall_mm": 65.0, "wind_kmph": 45.0, "humidity_pct": 98.0,
        "description": "Very heavy rainfall — waterlogging likely in low-lying areas",
        "visibility_km": 1.0, "pressure_hpa": 998.0, "cloud_cover_pct": 100.0,
    },
    {
        "name": "cold_wave",
        "temp_c": -6.0, "rainfall_mm": 2.0, "wind_kmph": 25.0, "humidity_pct": 60.0,
        "description": "Cold wave conditions — temperature 6°C below normal",
        "visibility_km": 5.0, "pressure_hpa": 1030.0, "cloud_cover_pct": 70.0,
    },
]

# Stable mapping: district name hash → scenario index (so same district always
# returns the same scenario within a session, giving consistent demo behavior)
def _get_scenario_for_district(district: str) -> dict:
    # Python's built-in hash is randomized between processes, which would make
    # a demo location return a different alert after every server restart.
    digest = hashlib.sha256(district.lower().strip().encode("utf-8")).digest()
    idx = int.from_bytes(digest[:8], "big") % len(_IMD_MOCK_SCENARIOS)
    return _IMD_MOCK_SCENARIOS[idx]


def get_imd_mock(district: str) -> WeatherSnapshot:
    """
    Return a realistic mock IMD bulletin for the given district.
    Shaped like a real IMD district-level forecast would be.
    """
    scenario = _get_scenario_for_district(district)
    alert_level, headline = _derive_alert_level(
        scenario["temp_c"], scenario["rainfall_mm"], scenario["wind_kmph"]
    )

    now = datetime.now(IST)
    # IMD bulletins are issued at standard synoptic times
    bulletin_time = now.replace(minute=0, second=0, microsecond=0)

    return WeatherSnapshot(
        location=district.title(),
        timestamp=bulletin_time,
        temp_c=scenario["temp_c"],
        feels_like_c=scenario["temp_c"] + random.uniform(-2, 3),
        rainfall_mm=scenario["rainfall_mm"],
        wind_kmph=scenario["wind_kmph"],
        wind_direction=random.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"]),
        humidity_pct=scenario["humidity_pct"],
        visibility_km=scenario["visibility_km"],
        pressure_hpa=scenario["pressure_hpa"],
        cloud_cover_pct=scenario["cloud_cover_pct"],
        alert_level=alert_level,
        alert_headline=headline,
        description=scenario["description"],
        source=f"imd_mock_{now.strftime('%Y-%m-%d')}",
    )


# =============================================================================
# SOURCE 3: MOSDAC Mock Feed
# =============================================================================

# ──────────────────────────────────────────────────────────────────────────
# To switch to real MOSDAC: replace this function body with an API call
# using approved MOSDAC credentials. This is the ONLY function to change.
# ──────────────────────────────────────────────────────────────────────────

_MOSDAC_MOCK_SCENARIOS = [
    {
        "name": "cyclone_track",
        "temp_c": 27.0, "rainfall_mm": 70.0, "wind_kmph": 140.0, "humidity_pct": 90.0,
        "description": "Satellite imagery shows well-defined cyclonic circulation — landfall expected within 24h",
        "visibility_km": 1.0, "pressure_hpa": 978.0, "cloud_cover_pct": 100.0,
    },
    {
        "name": "flood_inundation",
        "temp_c": 25.0, "rainfall_mm": 55.0, "wind_kmph": 30.0, "humidity_pct": 96.0,
        "description": "Satellite-derived flood map shows significant inundation in river basins",
        "visibility_km": 3.0, "pressure_hpa": 1000.0, "cloud_cover_pct": 90.0,
    },
    {
        "name": "cloudburst",
        "temp_c": 18.0, "rainfall_mm": 95.0, "wind_kmph": 50.0, "humidity_pct": 99.0,
        "description": "Cloud burst detected — extreme precipitation in localized area",
        "visibility_km": 0.5, "pressure_hpa": 992.0, "cloud_cover_pct": 100.0,
    },
    {
        "name": "normal_conditions",
        "temp_c": 30.0, "rainfall_mm": 5.0, "wind_kmph": 15.0, "humidity_pct": 55.0,
        "description": "Satellite shows normal cloud patterns with scattered convective activity",
        "visibility_km": 10.0, "pressure_hpa": 1012.0, "cloud_cover_pct": 40.0,
    },
    {
        "name": "drought_indicators",
        "temp_c": 38.0, "rainfall_mm": 0.0, "wind_kmph": 10.0, "humidity_pct": 20.0,
        "description": "Vegetation stress indices indicate drought conditions — soil moisture critically low",
        "visibility_km": 12.0, "pressure_hpa": 1010.0, "cloud_cover_pct": 10.0,
    },
]


def get_mosdac_mock(region: str) -> WeatherSnapshot:
    """
    Return realistic mock MOSDAC satellite-derived data for a region.
    """
    digest = hashlib.sha256(region.lower().strip().encode("utf-8")).digest()
    idx = int.from_bytes(digest[:8], "big") % len(_MOSDAC_MOCK_SCENARIOS)
    scenario = _MOSDAC_MOCK_SCENARIOS[idx]
    alert_level, headline = _derive_alert_level(
        scenario["temp_c"], scenario["rainfall_mm"], scenario["wind_kmph"]
    )

    now = datetime.now(IST)

    return WeatherSnapshot(
        location=region.title(),
        timestamp=now.replace(minute=0, second=0, microsecond=0),
        temp_c=scenario["temp_c"],
        rainfall_mm=scenario["rainfall_mm"],
        wind_kmph=scenario["wind_kmph"],
        humidity_pct=scenario["humidity_pct"],
        visibility_km=scenario["visibility_km"],
        pressure_hpa=scenario["pressure_hpa"],
        cloud_cover_pct=scenario["cloud_cover_pct"],
        alert_level=alert_level,
        alert_headline=headline,
        description=scenario["description"],
        source=f"mosdac_mock_{now.strftime('%Y-%m-%d')}",
    )


# =============================================================================
# UNIFIED: Get best weather data for a location
# =============================================================================

async def get_weather_for_location(location_str: str) -> WeatherSnapshot:
    """
    Get the best available weather data for a location string.
    Priority: OpenWeatherMap (live) > IMD mock > MOSDAC mock.
    Always returns a WeatherSnapshot (falls back to mocks if OWM unavailable).
    """
    lat, lon = await geocode_location(location_str)

    # Try live OWM first
    owm_data = await get_openweather(lat, lon)
    if owm_data is not None:
        return owm_data

    # Fall back to IMD mock (more detailed for Indian districts)
    # Extract the city/district name from the location string
    district = location_str.split(",")[0].strip()
    return get_imd_mock(district)
