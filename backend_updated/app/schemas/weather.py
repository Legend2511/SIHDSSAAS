"""
Weather data schemas — WeatherSnapshot and AlertLevel.

These are the core data models that all ingestion sources normalize into.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AlertLevel(str, Enum):
    """
    IMD-style alert levels.
    - Red:    Take action — extremely severe conditions expected
    - Orange: Be prepared — significantly bad weather expected
    - Yellow: Be aware — moderately bad weather possible
    - Green:  No alert — normal conditions
    """
    RED = "Red"
    ORANGE = "Orange"
    YELLOW = "Yellow"
    GREEN = "None"  # JSON-serializes as "None" to match API contract


class WeatherSnapshot(BaseModel):
    """
    Normalized weather data from any source (OWM, IMD, MOSDAC).

    This is the single data structure the LLM and guardrail receive —
    source-specific quirks are resolved during ingestion, not downstream.
    """
    location: str = Field(..., description="Human-readable location name")
    lat: Optional[float] = Field(None, description="Latitude")
    lon: Optional[float] = Field(None, description="Longitude")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    temp_c: float = Field(..., description="Temperature in Celsius")
    feels_like_c: Optional[float] = Field(None, description="Feels-like temperature in Celsius")
    rainfall_mm: float = Field(0.0, description="Rainfall in mm (last 1–3 hours)")
    wind_kmph: float = Field(0.0, description="Wind speed in km/h")
    wind_direction: Optional[str] = Field(None, description="Wind direction (e.g. 'NW')")
    humidity_pct: float = Field(0.0, description="Relative humidity %")
    visibility_km: Optional[float] = Field(None, description="Visibility in km")
    pressure_hpa: Optional[float] = Field(None, description="Atmospheric pressure in hPa")
    cloud_cover_pct: Optional[float] = Field(None, description="Cloud cover %")
    alert_level: AlertLevel = Field(AlertLevel.GREEN, description="Derived alert level")
    alert_headline: Optional[str] = Field(None, description="Short alert headline if any")
    description: str = Field("", description="Human-readable weather description")
    source: str = Field(..., description="Data source identifier")

    def summary_for_llm(self) -> str:
        """
        Compact text summary for inclusion in LLM prompts.
        Keeps token count low while giving the LLM all actionable facts.
        """
        parts = [
            f"Location: {self.location}",
            f"Time: {self.timestamp.strftime('%Y-%m-%d %H:%M UTC')}",
            f"Temperature: {self.temp_c}°C" + (f" (feels like {self.feels_like_c}°C)" if self.feels_like_c else ""),
            f"Humidity: {self.humidity_pct}%",
            f"Wind: {self.wind_kmph} km/h" + (f" {self.wind_direction}" if self.wind_direction else ""),
            f"Rainfall: {self.rainfall_mm} mm",
        ]
        if self.visibility_km is not None:
            parts.append(f"Visibility: {self.visibility_km} km")
        if self.pressure_hpa is not None:
            parts.append(f"Pressure: {self.pressure_hpa} hPa")
        parts.append(f"Conditions: {self.description}")
        parts.append(f"Alert Level: {self.alert_level.value}")
        if self.alert_headline:
            parts.append(f"Alert: {self.alert_headline}")
        parts.append(f"Source: {self.source}")
        return "\n".join(parts)
